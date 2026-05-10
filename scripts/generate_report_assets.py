import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
ASSET_DIR = BENCHMARK_DIR / "report_assets"
FIGURE_DIR = ASSET_DIR / "figures"
TABLE_DIR = ASSET_DIR / "tables"


COLORS = {
    "IELTS": "#2f6fbb",
    "TOEIC": "#2f9e73",
    "TOEFL": "#d9822b",
    "Cambridge": "#8b5cf6",
    "docTR_full_improved": "#2563eb",
    "PaddleOCR_full": "#14b8a6",
    "EasyOCR_full": "#f97316",
    "docTR_no_preprocessing": "#64748b",
}


def read_csv(path: Path) -> list[dict]:
    for encoding in ["utf-8-sig", "utf-8", "cp1258", "cp1252"]:
        try:
            with path.open("r", newline="", encoding=encoding) as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode {path}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            pass
    return ImageFont.load_default()


def save_bar_chart(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    ylabel: str = "",
    suffix: str = "",
    colors: list[str] | None = None,
    width: int = 1200,
    height: int = 760,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = font(34, True)
    label_font = font(23)
    value_font = font(22, True)
    axis_font = font(20)

    margin_left = 110
    margin_right = 60
    margin_top = 105
    margin_bottom = 145
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom
    max_value = max(values) if values else 1
    max_axis = max_value * 1.15 if max_value else 1

    draw.text((margin_left, 35), title, fill="#111827", font=title_font)
    if ylabel:
        draw.text((margin_left, 77), ylabel, fill="#64748b", font=axis_font)

    grid_color = "#e5e7eb"
    axis_color = "#334155"
    for i in range(6):
        y = margin_top + chart_h - (chart_h * i / 5)
        value = max_axis * i / 5
        draw.line((margin_left, y, width - margin_right, y), fill=grid_color, width=1)
        draw.text((20, y - 12), f"{value:.0f}", fill="#64748b", font=axis_font)
    draw.line((margin_left, margin_top, margin_left, margin_top + chart_h), fill=axis_color, width=2)
    draw.line((margin_left, margin_top + chart_h, width - margin_right, margin_top + chart_h), fill=axis_color, width=2)

    n = len(labels)
    gap = 26
    bar_w = max(28, int((chart_w - gap * (n + 1)) / max(1, n)))
    colors = colors or ["#2563eb"] * n
    for idx, (label, value) in enumerate(zip(labels, values)):
        x1 = margin_left + gap + idx * (bar_w + gap)
        x2 = x1 + bar_w
        bar_h = chart_h * (value / max_axis) if max_axis else 0
        y1 = margin_top + chart_h - bar_h
        y2 = margin_top + chart_h
        draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill=colors[idx])
        shown = f"{value:.2f}{suffix}" if isinstance(value, float) and not value.is_integer() else f"{int(value)}{suffix}"
        if suffix == "%":
            shown = f"{value:.1f}%"
        draw.text((x1 + bar_w / 2, y1 - 34), shown, fill="#111827", font=value_font, anchor="mm")
        draw.text((x1 + bar_w / 2, y2 + 35), label, fill="#111827", font=label_font, anchor="mm")

    img.save(path)


def save_grouped_bar_chart(
    path: Path,
    title: str,
    groups: list[str],
    series: list[tuple[str, list[float], str]],
    ylabel: str,
    suffix: str = "",
    width: int = 1350,
    height: int = 800,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = font(34, True)
    label_font = font(22)
    value_font = font(18, True)
    axis_font = font(20)

    margin_left = 110
    margin_right = 65
    margin_top = 125
    margin_bottom = 160
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom
    all_values = [v for _, vals, _ in series for v in vals]
    max_axis = (max(all_values) if all_values else 1) * 1.15

    draw.text((margin_left, 35), title, fill="#111827", font=title_font)
    draw.text((margin_left, 77), ylabel, fill="#64748b", font=axis_font)

    for i in range(6):
        y = margin_top + chart_h - (chart_h * i / 5)
        value = max_axis * i / 5
        draw.line((margin_left, y, width - margin_right, y), fill="#e5e7eb", width=1)
        draw.text((20, y - 12), f"{value:.0f}", fill="#64748b", font=axis_font)
    draw.line((margin_left, margin_top + chart_h, width - margin_right, margin_top + chart_h), fill="#334155", width=2)
    draw.line((margin_left, margin_top, margin_left, margin_top + chart_h), fill="#334155", width=2)

    group_gap = 52
    group_w = (chart_w - group_gap * (len(groups) + 1)) / len(groups)
    bar_gap = 8
    bar_w = (group_w - bar_gap * (len(series) - 1)) / len(series)

    for g_idx, group in enumerate(groups):
        gx = margin_left + group_gap + g_idx * (group_w + group_gap)
        for s_idx, (name, vals, color) in enumerate(series):
            value = vals[g_idx]
            x1 = gx + s_idx * (bar_w + bar_gap)
            x2 = x1 + bar_w
            bar_h = chart_h * (value / max_axis) if max_axis else 0
            y1 = margin_top + chart_h - bar_h
            y2 = margin_top + chart_h
            draw.rounded_rectangle((x1, y1, x2, y2), radius=6, fill=color)
            shown = f"{value:.1f}{suffix}" if suffix == "%" else f"{value:.1f}"
            draw.text((x1 + bar_w / 2, y1 - 24), shown, fill="#111827", font=value_font, anchor="mm")
        draw.text((gx + group_w / 2, margin_top + chart_h + 35), group, fill="#111827", font=label_font, anchor="mm")

    legend_x = margin_left
    legend_y = height - 70
    for name, _, color in series:
        draw.rounded_rectangle((legend_x, legend_y, legend_x + 30, legend_y + 18), radius=4, fill=color)
        draw.text((legend_x + 42, legend_y - 3), name, fill="#111827", font=axis_font)
        legend_x += 300
    img.save(path)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out) + "\n"


def latex_table(headers: list[str], rows: list[list[str]], caption: str, label: str) -> str:
    def tex(value: str) -> str:
        return str(value).replace("&", "\\&").replace("_", "\\_")

    cols = "l" + "r" * (len(headers) - 1)
    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{cols}}}",
        "\\hline",
        " & ".join(tex(header) for header in headers) + " \\\\",
        "\\hline",
    ]
    lines += [" & ".join(tex(cell) for cell in row) + " \\\\" for row in rows]
    lines += ["\\hline", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def write_table_pair(name: str, headers: list[str], rows: list[list[str]], caption: str, label: str) -> None:
    write_text(TABLE_DIR / f"{name}.md", markdown_table(headers, rows))
    write_text(TABLE_DIR / f"{name}.tex", latex_table(headers, rows, caption, label))


def display_config(value: str) -> str:
    return {
        "docTR_full_improved": "docTR",
        "PaddleOCR_full": "PaddleOCR",
        "EasyOCR_full": "EasyOCR",
        "docTR_no_preprocessing": "docTR (no preprocessing)",
    }.get(value, value.replace("_", " "))


def pct(value: str | float) -> str:
    return f"{float(value) * 100:.2f}\\%"


def main() -> int:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    dataset_rows = read_csv(BENCHMARK_DIR / "dataset_summary.csv")
    dataset_types = [r for r in dataset_rows if r["cert_type"] != "TOTAL"]
    labels = [r["cert_type"] for r in dataset_types]
    samples = [float(r["samples"]) for r in dataset_types]
    fields = [float(r["field_annotation_rows"]) for r in dataset_types]
    colors = [COLORS.get(label, "#2563eb") for label in labels]

    save_bar_chart(
        FIGURE_DIR / "dataset_samples_by_type.png",
        "EnglishCert-110 Samples by Certificate Type",
        labels,
        samples,
        "Number of documents",
        colors=colors,
    )
    save_bar_chart(
        FIGURE_DIR / "dataset_field_annotations_by_type.png",
        "Field Annotations by Certificate Type",
        labels,
        fields,
        "Number of annotated fields",
        colors=colors,
    )

    dataset_table_rows = [
        [
            r["cert_type"],
            r["samples"],
            r["jpg"],
            r["jpeg"],
            r["png"],
            r["fields_per_sample"],
            r["field_annotation_rows"],
        ]
        for r in dataset_types
    ]
    write_table_pair(
        "table_dataset_composition",
        ["Type", "Samples", "JPG", "JPEG", "PNG", "Fields/sample", "Rows"],
        dataset_table_rows,
        "EnglishCert-110 dataset composition.",
        "tab:dataset-composition",
    )

    comparison = read_csv(BENCHMARK_DIR / "results" / "comparison_overall.csv")
    comp_rows = [
        [
            display_config(r["config"]),
            r["samples"],
            pct(r["classification_accuracy"]),
            pct(r["field_normalized_accuracy"]),
            f"{float(r['avg_processing_ms']) / 1000:.2f}s",
        ]
        for r in comparison
    ]
    write_table_pair(
        "table_comparison_overall",
        ["Config", "Samples", "Classification", "Field Acc.", "Avg Time"],
        comp_rows,
        "Overall comparison of OCR and preprocessing configurations.",
        "tab:comparison-overall",
    )

    ocr_configs = ["docTR_full_improved", "PaddleOCR_full", "EasyOCR_full"]
    ocr = [r for r in comparison if r["config"] in set(ocr_configs)]
    write_table_pair(
        "table_ocr_comparison_overall",
        ["OCR Engine", "Samples", "Classification", "Field Acc.", "Avg Time"],
        [
            [
                display_config(r["config"]),
                r["samples"],
                pct(r["classification_accuracy"]),
                pct(r["field_normalized_accuracy"]),
                f"{float(r['avg_processing_ms']) / 1000:.2f}s",
            ]
            for r in ocr
        ],
        "Zero-shot OCR engine comparison on EnglishCert-110.",
        "tab:ocr-comparison-overall",
    )
    save_grouped_bar_chart(
        FIGURE_DIR / "ocr_comparison_accuracy_runtime.png",
        "OCR Engine Comparison",
        [display_config(r["config"]) for r in ocr],
        [
            ("Field accuracy (%)", [float(r["field_normalized_accuracy"]) * 100 for r in ocr], "#2563eb"),
            ("Avg time (s)", [float(r["avg_processing_ms"]) / 1000 for r in ocr], "#f97316"),
        ],
        "Field accuracy (%) and runtime (s)",
    )

    by_type = read_csv(BENCHMARK_DIR / "results" / "comparison_by_type.csv")
    cert_order = ["IELTS", "TOEIC", "TOEFL", "Cambridge"]
    ocr_by_type = [r for r in by_type if r["config"] in set(ocr_configs)]
    series_accuracy = []
    series_runtime = []
    for config in ocr_configs:
        rows_by_type = {r["cert_type"]: r for r in ocr_by_type if r["config"] == config}
        series_accuracy.append(
            (
                display_config(config),
                [float(rows_by_type[cert]["field_normalized_accuracy"]) * 100 for cert in cert_order],
                COLORS.get(config, "#2563eb"),
            )
        )
        series_runtime.append(
            (
                display_config(config),
                [float(rows_by_type[cert]["avg_processing_ms"]) / 1000 for cert in cert_order],
                COLORS.get(config, "#2563eb"),
            )
        )
    save_grouped_bar_chart(
        FIGURE_DIR / "ocr_accuracy_by_type.png",
        "OCR Field Accuracy by Certificate Type",
        cert_order,
        series_accuracy,
        "Normalized field accuracy (%)",
        "%",
    )
    save_grouped_bar_chart(
        FIGURE_DIR / "ocr_runtime_by_type.png",
        "OCR Runtime by Certificate Type",
        cert_order,
        series_runtime,
        "Average processing time (s)",
    )
    write_table_pair(
        "table_ocr_comparison_by_type",
        ["Engine", "Type", "Field Acc.", "Avg Time", "Missing"],
        [
            [
                display_config(r["config"]),
                r["cert_type"],
                pct(r["field_normalized_accuracy"]),
                f"{float(r['avg_processing_ms']) / 1000:.2f}s",
                r["missing_predictions"],
            ]
            for config in ocr_configs
            for r in ocr_by_type
            if r["config"] == config
        ],
        "OCR engine comparison by certificate type.",
        "tab:ocr-comparison-by-type",
    )

    doctr_type = [r for r in by_type if r["config"] == "docTR_full_improved"]
    save_bar_chart(
        FIGURE_DIR / "doctr_field_accuracy_by_type.png",
        "docTR Improved Field Accuracy by Type",
        [r["cert_type"] for r in doctr_type],
        [float(r["field_normalized_accuracy"]) * 100 for r in doctr_type],
        "Normalized field accuracy (%)",
        "%",
        [COLORS.get(r["cert_type"], "#2563eb") for r in doctr_type],
    )

    pre = [r for r in comparison if r["config"] in {"docTR_full_improved", "docTR_no_preprocessing"}]
    save_grouped_bar_chart(
        FIGURE_DIR / "preprocessing_ablation.png",
        "Preprocessing Ablation",
        [r["config"].replace("_", " ") for r in pre],
        [
            ("Field accuracy (%)", [float(r["field_normalized_accuracy"]) * 100 for r in pre], "#2563eb"),
            ("Avg time (s)", [float(r["avg_processing_ms"]) / 1000 for r in pre], "#64748b"),
        ],
        "Field accuracy (%) and runtime (s)",
    )

    improvement = read_csv(BENCHMARK_DIR / "results" / "extraction_improvement_by_type.csv")
    save_grouped_bar_chart(
        FIGURE_DIR / "extraction_improvement_by_type.png",
        "Extraction Rule Improvement",
        [r["cert_type"] for r in improvement],
        [
            ("Baseline (%)", [float(r["baseline_normalized_accuracy"]) * 100 for r in improvement], "#94a3b8"),
            ("Improved (%)", [float(r["improved_normalized_accuracy"]) * 100 for r in improvement], "#2563eb"),
        ],
        "Normalized field accuracy (%)",
        "%",
    )
    write_table_pair(
        "table_extraction_improvement_by_type",
        ["Type", "Baseline", "Improved", "Delta"],
        [
            [
                r["cert_type"],
                pct(r["baseline_normalized_accuracy"]),
                pct(r["improved_normalized_accuracy"]),
                f"{float(r['delta']) * 100:+.2f} pp",
            ]
            for r in improvement
        ],
        "Effect of extraction rule improvements.",
        "tab:extraction-improvement",
    )

    field_metrics = read_csv(BENCHMARK_DIR / "metrics_doctr_improved2" / "field_metrics.csv")
    weak = sorted(field_metrics, key=lambda r: float(r["normalized_accuracy"]))[:12]
    save_bar_chart(
        FIGURE_DIR / "weakest_fields_doctr.png",
        "Weakest Fields after docTR Improvement",
        [f"{r['cert_type']}\n{r['field_key'].split('.')[-1]}" for r in weak],
        [float(r["normalized_accuracy"]) * 100 for r in weak],
        "Normalized field accuracy (%)",
        "%",
        ["#dc2626"] * len(weak),
        width=1500,
    )
    write_table_pair(
        "table_weakest_fields",
        ["Type", "Field", "Samples", "Accuracy", "Missing"],
        [[r["cert_type"], r["field_key"], r["samples"], pct(r["normalized_accuracy"]), r["missing_predictions"]] for r in weak],
        "Lowest-accuracy fields after improvements.",
        "tab:weakest-fields",
    )

    print(f"Wrote figures to {FIGURE_DIR}")
    print(f"Wrote tables to {TABLE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
