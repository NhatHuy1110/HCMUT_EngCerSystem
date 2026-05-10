import argparse
import csv
import json
import sys
import time
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from core.pipeline import process_document  # noqa: E402


def read_csv(path: Path) -> list[dict]:
    for encoding in ["utf-8-sig", "utf-8", "cp1258", "cp1252"]:
        try:
            with path.open("r", newline="", encoding=encoding) as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode CSV file: {path}")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def warning_text(value) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


def load_ground_truth(path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    if not path or not path.exists():
        return {}
    rows = read_csv(path)
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        out[(row.get("sample_id", ""), row.get("field_key", ""))] = {
            "ground_truth_value": row.get("ground_truth_value", ""),
            "not_present": row.get("not_present", ""),
            "annotation_note": row.get("annotation_note", ""),
        }
    return out


def process_sample(
    row: dict,
    data_dir: Path,
    engine: str,
    preprocessing: str,
    ground_truth_by_field: dict[tuple[str, str], dict[str, str]],
) -> tuple[dict, list[dict]]:
    sample_id = row["sample_id"]
    expected_type = row["cert_type"]
    relative_path = row["relative_path"]
    image_path = data_dir / relative_path

    started = time.perf_counter()
    result = process_document(image_path.read_bytes(), image_path.name, engine, preprocessing)
    wall_ms = int((time.perf_counter() - started) * 1000)

    quality = result.get("quality", {})
    ocr = result.get("ocr", {})
    predicted_type = result.get("certType", "")
    sample_out = {
        "sample_id": sample_id,
        "expected_type": expected_type,
        "relative_path": relative_path,
        "file_name": row["file_name"],
        "engine_requested": engine,
        "engine_used": ocr.get("engine", ""),
        "preprocessing": result.get("preprocessingMode", preprocessing),
        "predicted_type": predicted_type,
        "classification_confidence": result.get("confidence", 0),
        "classification_correct": int(predicted_type == expected_type),
        "processing_ms_reported": result.get("processingMs", 0),
        "processing_ms_wall": wall_ms,
        "ocr_word_count": ocr.get("word_count", 0),
        "ocr_mean_confidence": ocr.get("mean_confidence", 0),
        "total_fields": quality.get("total_fields", 0),
        "valid_fields": quality.get("valid_fields", 0),
        "review_fields": quality.get("review_fields", 0),
        "missing_required": quality.get("missing_required", 0),
        "low_confidence": quality.get("low_confidence", 0),
        "completion_rate": quality.get("completion_rate", 0),
        "warnings": warning_text(result.get("warnings", [])),
        "error": "",
    }

    field_rows = []
    for field in result.get("fields", []):
        existing_gt = ground_truth_by_field.get((sample_id, field.get("key", "")), {})
        field_rows.append(
            {
                "sample_id": sample_id,
                "expected_type": expected_type,
                "predicted_type": predicted_type,
                "relative_path": relative_path,
                "file_name": row["file_name"],
                "field_key": field.get("key", ""),
                "field_label": field.get("label", ""),
                "required": str(field.get("required", "")).lower(),
                "predicted_value": field.get("value", ""),
                "predicted_status": field.get("status", ""),
                "predicted_confidence": field.get("confidence", ""),
                "source": field.get("source", ""),
                "field_warnings": warning_text(field.get("warnings", [])),
                "evidence": field.get("evidence", ""),
                "ground_truth_value": existing_gt.get("ground_truth_value", ""),
                "not_present": existing_gt.get("not_present", ""),
                "annotation_note": existing_gt.get("annotation_note", ""),
            }
        )
    return sample_out, field_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT.parent / "Data_ĐACN"))
    parser.add_argument("--manifest", default=str(PROJECT_ROOT / "benchmark" / "benchmark_manifest.csv"))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "benchmark" / "predictions"))
    parser.add_argument("--engine", default="doctr")
    parser.add_argument("--preprocessing", choices=["full", "none"], default="full")
    parser.add_argument("--ground-truth", default="")
    parser.add_argument("--cert-type", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    manifest_path = Path(args.manifest).resolve()
    out_dir = Path(args.out_dir).resolve()
    engine_slug = args.engine.lower().replace("-", "_")

    manifest_rows = read_csv(manifest_path)
    if args.cert_type:
        requested_type = args.cert_type.strip().lower()
        manifest_rows = [
            row for row in manifest_rows if row.get("cert_type", "").strip().lower() == requested_type
        ]
    if args.limit:
        manifest_rows = manifest_rows[: args.limit]
    ground_truth_path = Path(args.ground_truth).resolve() if args.ground_truth else None
    ground_truth_by_field = load_ground_truth(ground_truth_path)

    sample_rows: list[dict] = []
    field_rows: list[dict] = []
    error_rows: list[dict] = []

    for index, row in enumerate(manifest_rows, start=1):
        print(
            f"[{index:03d}/{len(manifest_rows):03d}] {row['sample_id']} {row['relative_path']}",
            flush=True,
        )
        started = time.perf_counter()
        try:
            sample_out, sample_fields = process_sample(row, data_dir, args.engine, args.preprocessing, ground_truth_by_field)
            sample_rows.append(sample_out)
            field_rows.extend(sample_fields)
            print(
                f"  -> type={sample_out['predicted_type']} "
                f"correct={sample_out['classification_correct']} "
                f"valid={sample_out['valid_fields']}/{sample_out['total_fields']} "
                f"time={sample_out['processing_ms_reported']}ms",
                flush=True,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            error = {
                "sample_id": row["sample_id"],
                "expected_type": row["cert_type"],
                "relative_path": row["relative_path"],
                "file_name": row["file_name"],
                "engine_requested": args.engine,
                "error": str(exc),
                "processing_ms_wall": elapsed_ms,
            }
            error_rows.append(error)
            sample_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "expected_type": row["cert_type"],
                    "relative_path": row["relative_path"],
                    "file_name": row["file_name"],
                    "engine_requested": args.engine,
                    "engine_used": "",
                    "preprocessing": args.preprocessing,
                    "predicted_type": "",
                    "classification_confidence": 0,
                    "classification_correct": 0,
                    "processing_ms_reported": 0,
                    "processing_ms_wall": elapsed_ms,
                    "ocr_word_count": 0,
                    "ocr_mean_confidence": 0,
                    "total_fields": 0,
                    "valid_fields": 0,
                    "review_fields": 0,
                    "missing_required": 0,
                    "low_confidence": 0,
                    "completion_rate": 0,
                    "warnings": "",
                    "error": str(exc),
                }
            )
            print(f"  -> ERROR {exc}", flush=True)

    sample_fieldnames = [
        "sample_id",
        "expected_type",
        "relative_path",
        "file_name",
        "engine_requested",
        "engine_used",
        "preprocessing",
        "predicted_type",
        "classification_confidence",
        "classification_correct",
        "processing_ms_reported",
        "processing_ms_wall",
        "ocr_word_count",
        "ocr_mean_confidence",
        "total_fields",
        "valid_fields",
        "review_fields",
        "missing_required",
        "low_confidence",
        "completion_rate",
        "warnings",
        "error",
    ]
    field_fieldnames = [
        "sample_id",
        "expected_type",
        "predicted_type",
        "relative_path",
        "file_name",
        "field_key",
        "field_label",
        "required",
        "predicted_value",
        "predicted_status",
        "predicted_confidence",
        "source",
        "field_warnings",
        "evidence",
        "ground_truth_value",
        "not_present",
        "annotation_note",
    ]
    error_fieldnames = [
        "sample_id",
        "expected_type",
        "relative_path",
        "file_name",
        "engine_requested",
        "error",
        "processing_ms_wall",
    ]

    write_csv(out_dir / f"samples_{engine_slug}.csv", sample_rows, sample_fieldnames)
    write_csv(out_dir / f"fields_prefill_{engine_slug}.csv", field_rows, field_fieldnames)
    write_csv(out_dir / f"errors_{engine_slug}.csv", error_rows, error_fieldnames)

    summary = {
        "engine": args.engine,
        "samples": len(sample_rows),
        "errors": len(error_rows),
        "classification_accuracy": (
            sum(int(row["classification_correct"]) for row in sample_rows) / len(sample_rows)
            if sample_rows
            else 0
        ),
        "avg_processing_ms_reported": (
            sum(int(row["processing_ms_reported"] or 0) for row in sample_rows) / len(sample_rows)
            if sample_rows
            else 0
        ),
    }
    (out_dir / f"summary_{engine_slug}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if not error_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
