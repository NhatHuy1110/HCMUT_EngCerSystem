import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%m-%d-%y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d-%b-%y",
    "%d-%B-%y",
    "%d/%b/%Y",
    "%d/%B/%Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b %y",
    "%d %B %y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d, %y",
    "%B %d, %y",
    "%b %Y",
    "%B %Y",
    "%b-%y",
    "%B-%y",
    "%b/%y",
    "%B/%y",
    "%b %y",
    "%B %y",
]


def read_csv(path: Path) -> list[dict]:
    errors = []
    for encoding in ["utf-8-sig", "utf-8", "cp1258", "cp1252"]:
        try:
            with path.open("r", newline="", encoding=encoding) as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise UnicodeDecodeError(
        "utf-8",
        b"",
        0,
        1,
        f"Could not decode {path}. Tried utf-8-sig, utf-8, cp1258, cp1252. {' | '.join(errors)}",
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_date(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    if not value:
        return ""
    value = value.replace("SEPT", "SEP")
    value = re.sub(r"^(\d{1,2})/([A-Za-z]{3,9})/(\d{2})$", r"\1/\2/20\3", value, flags=re.I)
    value = re.sub(r"^(\d{1,2})-([A-Za-z]{3,9})-(\d{2})$", r"\1-\2-20\3", value, flags=re.I)
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value.title(), fmt)
            if "%d" not in fmt:
                return parsed.strftime("%Y-%m")
            return parsed.strftime("%Y-%m-%d")
        except Exception:
            pass
    month_match = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{4})", value)
    if month_match:
        for fmt in ["%b %Y", "%B %Y"]:
            try:
                return datetime.strptime(value.title(), fmt).strftime("%Y-%m")
            except Exception:
                pass
    return ""


def normalize_value(value: str, field_key: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""

    if field_key.endswith("_date") or field_key.endswith(".test_date") or field_key.endswith(".birth_date"):
        parsed = parse_date(value)
        if parsed:
            return parsed

    if field_key.startswith("score."):
        cleaned = value.replace(",", ".")
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        if match:
            number = float(match.group(0))
            if abs(number - round(number)) < 0.001:
                return str(int(round(number)))
            return f"{number:.1f}".rstrip("0").rstrip(".")

    if field_key.endswith(".id") or field_key == "certificate.number":
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    if field_key in {"cefr.level", "grade"}:
        return re.sub(r"\s+", " ", value.upper())

    value = value.upper()
    value = re.sub(r"[^A-Z0-9À-Ỹ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_not_present(row: dict) -> bool:
    marker = str(row.get("not_present", "")).strip().lower()
    return marker in {"1", "true", "yes", "y", "na", "n/a"}


def evaluate_fields(prediction_rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    detailed_rows: list[dict] = []
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for row in prediction_rows:
        ground_truth = str(row.get("ground_truth_value", "") or "").strip()
        not_present = is_not_present(row)
        if not ground_truth and not not_present:
            continue

        predicted = str(row.get("predicted_value", "") or "").strip()
        field_key = row.get("field_key", "")
        expected_norm = "" if not_present else normalize_value(ground_truth, field_key)
        predicted_norm = normalize_value(predicted, field_key)
        exact_match = int((not_present and not predicted) or predicted == ground_truth)
        normalized_match = int((not_present and not predicted_norm) or predicted_norm == expected_norm)

        out = {
            "sample_id": row.get("sample_id", ""),
            "expected_type": row.get("expected_type", ""),
            "predicted_type": row.get("predicted_type", ""),
            "field_key": field_key,
            "field_label": row.get("field_label", ""),
            "predicted_value": predicted,
            "ground_truth_value": ground_truth,
            "predicted_norm": predicted_norm,
            "ground_truth_norm": expected_norm,
            "exact_match": exact_match,
            "normalized_match": normalized_match,
            "predicted_status": row.get("predicted_status", ""),
            "predicted_confidence": row.get("predicted_confidence", ""),
            "not_present": int(not_present),
        }
        detailed_rows.append(out)
        grouped[(out["expected_type"], field_key)].append(out)

    field_metrics = []
    for (cert_type, field_key), rows in sorted(grouped.items()):
        total = len(rows)
        field_metrics.append(
            {
                "cert_type": cert_type,
                "field_key": field_key,
                "samples": total,
                "exact_accuracy": round(sum(row["exact_match"] for row in rows) / total, 6) if total else 0,
                "normalized_accuracy": round(sum(row["normalized_match"] for row in rows) / total, 6) if total else 0,
                "missing_predictions": sum(1 for row in rows if not row["predicted_norm"]),
            }
        )

    type_groups: dict[str, list[dict]] = defaultdict(list)
    for row in detailed_rows:
        type_groups[row["expected_type"]].append(row)
    type_metrics = []
    for cert_type, rows in sorted(type_groups.items()):
        total = len(rows)
        type_metrics.append(
            {
                "cert_type": cert_type,
                "field_rows": total,
                "exact_accuracy": round(sum(row["exact_match"] for row in rows) / total, 6) if total else 0,
                "normalized_accuracy": round(sum(row["normalized_match"] for row in rows) / total, 6) if total else 0,
                "missing_predictions": sum(1 for row in rows if not row["predicted_norm"]),
            }
        )
    return detailed_rows, field_metrics, type_metrics


def build_mismatch_rows(detailed_rows: list[dict]) -> list[dict]:
    rows = []
    for row in detailed_rows:
        if int(row["normalized_match"]):
            continue
        if not row["predicted_norm"] and row["ground_truth_norm"]:
            reason = "missing_prediction"
        elif row["predicted_norm"] and not row["ground_truth_norm"]:
            reason = "predicted_but_not_present"
        elif row["field_key"].startswith("score."):
            reason = "score_mismatch"
        elif row["field_key"].endswith("_date") or row["field_key"].endswith(".test_date") or row["field_key"].endswith(".birth_date"):
            reason = "date_mismatch"
        elif row["field_key"].endswith(".id") or row["field_key"] == "certificate.number":
            reason = "identifier_mismatch"
        else:
            reason = "text_mismatch"
        rows.append(
            {
                "sample_id": row["sample_id"],
                "expected_type": row["expected_type"],
                "predicted_type": row["predicted_type"],
                "field_key": row["field_key"],
                "field_label": row["field_label"],
                "predicted_value": row["predicted_value"],
                "ground_truth_value": row["ground_truth_value"],
                "predicted_norm": row["predicted_norm"],
                "ground_truth_norm": row["ground_truth_norm"],
                "predicted_status": row["predicted_status"],
                "predicted_confidence": row["predicted_confidence"],
                "reason": reason,
            }
        )
    return rows


def evaluate_samples(sample_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in sample_rows:
        by_type[row.get("expected_type", "")].append(row)

    rows = []
    for cert_type, subset in sorted(by_type.items()):
        total = len(subset)
        rows.append(
            {
                "cert_type": cert_type,
                "samples": total,
                "classification_accuracy": round(
                    sum(int(row.get("classification_correct") or 0) for row in subset) / total,
                    6,
                )
                if total
                else 0,
                "avg_processing_ms": round(
                    sum(float(row.get("processing_ms_reported") or 0) for row in subset) / total,
                    2,
                )
                if total
                else 0,
                "avg_completion_rate": round(
                    sum(float(row.get("completion_rate") or 0) for row in subset) / total,
                    6,
                )
                if total
                else 0,
                "review_fields": sum(int(row.get("review_fields") or 0) for row in subset),
                "missing_required": sum(int(row.get("missing_required") or 0) for row in subset),
            }
        )

    confusion_counts: dict[tuple[str, str], int] = defaultdict(int)
    labels = sorted({row.get("expected_type", "") for row in sample_rows} | {row.get("predicted_type", "") for row in sample_rows})
    for row in sample_rows:
        confusion_counts[(row.get("expected_type", ""), row.get("predicted_type", ""))] += 1
    confusion_rows = []
    for expected in labels:
        if not expected:
            continue
        out = {"expected_type": expected}
        for predicted in labels:
            if predicted:
                out[predicted] = confusion_counts[(expected, predicted)]
        confusion_rows.append(out)
    return rows, confusion_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-predictions", default=str(PROJECT_ROOT / "benchmark" / "predictions" / "samples_doctr.csv"))
    parser.add_argument("--field-predictions", default=str(PROJECT_ROOT / "benchmark" / "predictions" / "fields_prefill_doctr.csv"))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "benchmark" / "metrics"))
    args = parser.parse_args()

    sample_rows = read_csv(Path(args.sample_predictions))
    field_rows = read_csv(Path(args.field_predictions))
    out_dir = Path(args.out_dir)

    detailed_rows, field_metrics, type_field_metrics = evaluate_fields(field_rows)
    mismatch_rows = build_mismatch_rows(detailed_rows)
    sample_metrics, confusion_rows = evaluate_samples(sample_rows)

    write_csv(
        out_dir / "field_detailed_matches.csv",
        detailed_rows,
        [
            "sample_id",
            "expected_type",
            "predicted_type",
            "field_key",
            "field_label",
            "predicted_value",
            "ground_truth_value",
            "predicted_norm",
            "ground_truth_norm",
            "exact_match",
            "normalized_match",
            "predicted_status",
            "predicted_confidence",
            "not_present",
        ],
    )
    write_csv(
        out_dir / "field_metrics.csv",
        field_metrics,
        ["cert_type", "field_key", "samples", "exact_accuracy", "normalized_accuracy", "missing_predictions"],
    )
    write_csv(
        out_dir / "type_field_metrics.csv",
        type_field_metrics,
        ["cert_type", "field_rows", "exact_accuracy", "normalized_accuracy", "missing_predictions"],
    )
    write_csv(
        out_dir / "field_mismatches.csv",
        mismatch_rows,
        [
            "sample_id",
            "expected_type",
            "predicted_type",
            "field_key",
            "field_label",
            "predicted_value",
            "ground_truth_value",
            "predicted_norm",
            "ground_truth_norm",
            "predicted_status",
            "predicted_confidence",
            "reason",
        ],
    )
    write_csv(
        out_dir / "sample_metrics.csv",
        sample_metrics,
        [
            "cert_type",
            "samples",
            "classification_accuracy",
            "avg_processing_ms",
            "avg_completion_rate",
            "review_fields",
            "missing_required",
        ],
    )
    if confusion_rows:
        write_csv(out_dir / "classification_confusion_matrix.csv", confusion_rows, list(confusion_rows[0].keys()))

    summary = {
        "annotated_field_rows": len(detailed_rows),
        "field_mismatches": len(mismatch_rows),
        "sample_metric_rows": len(sample_metrics),
        "field_metric_rows": len(field_metrics),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
