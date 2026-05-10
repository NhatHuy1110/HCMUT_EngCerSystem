import argparse
import csv
import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from core.pipeline import process_document  # noqa: E402


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
FIELD_COUNTS = {
    "IELTS": 11,
    "TOEIC": 8,
}


def iter_samples(data_dir: Path, cert_type: str) -> list[Path]:
    folder = data_dir / cert_type
    return sorted(
        [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda path: path.name.lower(),
    )


def row_from_result(expected_type: str, path: Path, result: dict, elapsed_ms: int) -> dict:
    quality = result.get("quality", {})
    fields = result.get("fields", [])
    entries = result.get("entries", {})
    correct_type = result.get("certType") == expected_type
    expected_fields = FIELD_COUNTS[expected_type]
    valid_fields = int(quality.get("valid_fields", 0) or 0)

    return {
        "dataset": expected_type,
        "file": path.name,
        "predicted_type": result.get("certType", ""),
        "classification_confidence": result.get("confidence", 0),
        "classification_correct": int(correct_type),
        "field_valid_proxy": valid_fields,
        "field_total_expected": expected_fields,
        "field_proxy_accuracy": round(valid_fields / expected_fields, 6),
        "pipeline_total_fields": int(quality.get("total_fields", len(fields)) or 0),
        "pipeline_review_fields": int(quality.get("review_fields", 0) or 0),
        "pipeline_missing_required": int(quality.get("missing_required", 0) or 0),
        "ocr_engine": result.get("ocr", {}).get("engine", ""),
        "ocr_word_count": result.get("ocr", {}).get("word_count", 0),
        "processing_ms_reported": result.get("processingMs", 0),
        "processing_ms_wall": elapsed_ms,
        "warnings": " | ".join(result.get("warnings", [])),
        "entries_json": json.dumps(entries, ensure_ascii=False, sort_keys=True),
        "fields_json": json.dumps(fields, ensure_ascii=False, sort_keys=True),
    }


def summarize(rows: list[dict]) -> dict:
    summary: dict[str, dict] = {}
    for cert_type in FIELD_COUNTS:
        subset = [row for row in rows if row["dataset"] == cert_type]
        expected_fields = FIELD_COUNTS[cert_type]
        sample_count = len(subset)
        denominator = expected_fields * sample_count
        classification_correct = sum(int(row["classification_correct"]) for row in subset)
        proxy_points = sum(int(row["field_valid_proxy"]) for row in subset)
        processing = [int(row["processing_ms_reported"] or 0) for row in subset]
        summary[cert_type] = {
            "samples": sample_count,
            "fields_per_sample": expected_fields,
            "field_denominator": denominator,
            "classification_correct": classification_correct,
            "classification_total": sample_count,
            "classification_accuracy": round(classification_correct / sample_count, 6) if sample_count else 0,
            "extraction_valid_proxy_points": proxy_points,
            "extraction_valid_proxy_denominator": denominator,
            "extraction_valid_proxy_accuracy": round(proxy_points / denominator, 6) if denominator else 0,
            "avg_processing_ms": round(sum(processing) / len(processing), 2) if processing else 0,
            "min_processing_ms": min(processing) if processing else 0,
            "max_processing_ms": max(processing) if processing else 0,
        }
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_manual_scoring_template(path: Path, rows: list[dict]) -> None:
    out_rows = []
    for row in rows:
        fields = json.loads(row["fields_json"])
        for field in fields:
            out_rows.append(
                {
                    "dataset": row["dataset"],
                    "file": row["file"],
                    "field_key": field.get("key", ""),
                    "field_label": field.get("label", ""),
                    "predicted_value": field.get("value", ""),
                    "predicted_status": field.get("status", ""),
                    "predicted_confidence": field.get("confidence", ""),
                    "source": field.get("source", ""),
                    "ground_truth_value": "",
                    "manual_score_0_or_1": "",
                    "note": "",
                }
            )
    write_csv(path, out_rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT.parent / "Data_ĐACN"))
    parser.add_argument("--engine", default="doctr")
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "eval_outputs"))
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    errors = []
    for cert_type in FIELD_COUNTS:
        samples = iter_samples(data_dir, cert_type)
        print(f"{cert_type}: {len(samples)} samples", flush=True)
        for index, path in enumerate(samples, start=1):
            started = time.perf_counter()
            try:
                result = process_document(path.read_bytes(), path.name, args.engine)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                row = row_from_result(cert_type, path, result, elapsed_ms)
                rows.append(row)
                print(
                    f"[{cert_type} {index:02d}/{len(samples):02d}] {path.name}: "
                    f"type={row['predicted_type']} class={row['classification_correct']} "
                    f"valid_proxy={row['field_valid_proxy']}/{row['field_total_expected']} "
                    f"time={row['processing_ms_reported']}ms",
                    flush=True,
                )
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                errors.append(
                    {
                        "dataset": cert_type,
                        "file": path.name,
                        "error": str(exc),
                        "processing_ms_wall": elapsed_ms,
                    }
                )
                print(f"[ERROR] {cert_type} {path.name}: {exc}", flush=True)

    summary = summarize(rows)
    write_csv(out_dir / "predictions.csv", rows)
    write_manual_scoring_template(out_dir / "manual_scoring_template.csv", rows)
    with (out_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "errors": errors}, handle, ensure_ascii=False, indent=2)

    print(json.dumps({"summary": summary, "errors": errors}, ensure_ascii=False, indent=2), flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
