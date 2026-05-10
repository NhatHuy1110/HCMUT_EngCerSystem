import argparse
import csv
import re
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from extraction.schema import get_schema  # noqa: E402


CERTIFICATE_TYPES = ["IELTS", "TOEIC", "TOEFL", "CAMBRIDGE"]
SCHEMA_TYPES = {"CAMBRIDGE": "Cambridge"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
EXPECTED_COUNTS = {
    "IELTS": 50,
    "TOEIC": 30,
    "TOEFL": 15,
    "CAMBRIDGE": 15,
}


def natural_key(path: Path) -> list[object]:
    name = path.name.lower()
    name = name.replace("sample_", "sample")
    name = re.sub(r"(?:^|[_-])sample(\.[^.]+)$", r"_sample1\1", name)
    parts = re.split(r"(\d+)", name)
    return [int(part) if part.isdigit() else part for part in parts]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows to write for {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def collect_manifest(data_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for cert_type in CERTIFICATE_TYPES:
        folder = data_dir / cert_type
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing dataset folder: {folder}")

        files = sorted(
            [
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ],
            key=natural_key,
        )

        expected = EXPECTED_COUNTS[cert_type]
        if len(files) != expected:
            raise ValueError(
                f"{cert_type} expected {expected} top-level image files, found {len(files)}. "
                "Check for missing files or unexpected top-level images."
            )

        for index, path in enumerate(files, start=1):
            rows.append(
                {
                    "sample_id": f"{cert_type}_{index:03d}",
                    "cert_type": SCHEMA_TYPES.get(cert_type, cert_type),
                    "dataset_folder": cert_type,
                    "relative_path": path.relative_to(data_dir).as_posix(),
                    "file_name": path.name,
                    "extension": path.suffix.lower(),
                    "subset": "benchmark",
                    "include_in_main_benchmark": "yes",
                    "notes": "",
                }
            )
    return rows


def build_ground_truth_template(manifest_rows: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for sample in manifest_rows:
        specs = get_schema(sample["cert_type"])
        if not specs:
            raise ValueError(f"No schema found for {sample['cert_type']}")
        for spec in specs:
            rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "cert_type": sample["cert_type"],
                    "relative_path": sample["relative_path"],
                    "file_name": sample["file_name"],
                    "field_key": spec.key,
                    "field_label": spec.label,
                    "required": str(spec.required).lower(),
                    "ground_truth_value": "",
                    "not_present": "",
                    "note": "",
                }
            )
    return rows


def build_summary_rows(manifest_rows: list[dict]) -> list[dict]:
    rows = []
    for cert_type in ["IELTS", "TOEIC", "TOEFL", "Cambridge"]:
        subset = [row for row in manifest_rows if row["cert_type"] == cert_type]
        rows.append(
            {
                "cert_type": cert_type,
                "samples": len(subset),
                "jpg": sum(1 for row in subset if row["extension"] == ".jpg"),
                "jpeg": sum(1 for row in subset if row["extension"] == ".jpeg"),
                "png": sum(1 for row in subset if row["extension"] == ".png"),
                "pdf": 0,
                "fields_per_sample": len(get_schema(cert_type)),
                "field_annotation_rows": len(subset) * len(get_schema(cert_type)),
            }
        )
    rows.append(
        {
            "cert_type": "TOTAL",
            "samples": len(manifest_rows),
            "jpg": sum(1 for row in manifest_rows if row["extension"] == ".jpg"),
            "jpeg": sum(1 for row in manifest_rows if row["extension"] == ".jpeg"),
            "png": sum(1 for row in manifest_rows if row["extension"] == ".png"),
            "pdf": 0,
            "fields_per_sample": "",
            "field_annotation_rows": sum(
                len(get_schema(row["cert_type"])) for row in manifest_rows
            ),
        }
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT.parent / "Data_ĐACN"))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "benchmark"))
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    out_dir = Path(args.out_dir).resolve()

    manifest_rows = collect_manifest(data_dir)
    ground_truth_rows = build_ground_truth_template(manifest_rows)
    summary_rows = build_summary_rows(manifest_rows)

    write_csv(out_dir / "benchmark_manifest.csv", manifest_rows)
    write_csv(out_dir / "ground_truth_template.csv", ground_truth_rows)
    write_csv(out_dir / "dataset_summary.csv", summary_rows)

    print(f"Wrote {len(manifest_rows)} manifest rows to {out_dir / 'benchmark_manifest.csv'}")
    print(f"Wrote {len(ground_truth_rows)} annotation rows to {out_dir / 'ground_truth_template.csv'}")
    print(f"Wrote dataset summary to {out_dir / 'dataset_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
