import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
ASSET_DIR = BENCHMARK_DIR / "report_assets"
FIGURE_DIR = ASSET_DIR / "figures_research"


CERT_ORDER = ["IELTS", "TOEIC", "TOEFL", "Cambridge"]
OCR_ORDER = ["docTR_full_improved", "PaddleOCR_full", "EasyOCR_full"]
OCR_LABELS = {
    "docTR_full_improved": "docTR",
    "PaddleOCR_full": "PaddleOCR",
    "EasyOCR_full": "EasyOCR",
    "docTR_no_preprocessing": "docTR no-prep",
}
CERT_COLORS = {
    "IELTS": "#2F6FDB",
    "TOEIC": "#16A34A",
    "TOEFL": "#F97316",
    "Cambridge": "#8B5CF6",
}
ENGINE_COLORS = {
    "docTR_full_improved": "#2563EB",
    "PaddleOCR_full": "#14B8A6",
    "EasyOCR_full": "#F97316",
    "docTR_no_preprocessing": "#64748B",
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
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            pass
    return ImageFont.load_default()


TITLE = font(44, True)
SUBTITLE = font(23)
H2 = font(28, True)
BODY = font(22)
BODY_BOLD = font(22, True)
SMALL = font(18)
SMALL_BOLD = font(18, True)
TINY = font(15)


def canvas(width: int = 1600, height: int = 1000) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (width, height), "#F8FAFC")
    return image, ImageDraw.Draw(image)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str = "#E2E8F0", radius: int = 22, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fnt=BODY, fill: str = "#0F172A", anchor: str | None = None) -> None:
    draw.text(xy, value, font=fnt, fill=fill, anchor=anchor)


def centered_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], value: str, fnt=BODY, fill: str = "#0F172A") -> None:
    x1, y1, x2, y2 = box
    draw.multiline_text(((x1 + x2) / 2, (y1 + y2) / 2), value, font=fnt, fill=fill, anchor="mm", align="center", spacing=6)


def save(image: Image.Image, name: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    image.save(FIGURE_DIR / name)


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * max(0, min(1, t)))


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{v:02x}" for v in rgb)


def blend(c1: str, c2: str, t: float) -> str:
    a = hex_to_rgb(c1)
    b = hex_to_rgb(c2)
    return rgb_to_hex(tuple(lerp(a[i], b[i], t) for i in range(3)))


def quality_color(value: float) -> str:
    if value < 0.55:
        return blend("#FEE2E2", "#FB923C", value / 0.55)
    if value < 0.85:
        return blend("#FED7AA", "#FDE68A", (value - 0.55) / 0.30)
    return blend("#D1FAE5", "#22C55E", (value - 0.85) / 0.15)


def runtime_color(value: float, minimum: float, maximum: float) -> str:
    t = 0 if maximum == minimum else (value - minimum) / (maximum - minimum)
    return blend("#DCFCE7", "#FDBA74", t)


def legend(draw: ImageDraw.ImageDraw, items: list[tuple[str, str]], x: int, y: int) -> None:
    current = x
    for label, color in items:
        draw.rounded_rectangle((current, y, current + 30, y + 18), radius=5, fill=color)
        text(draw, (current + 40, y - 4), label, SMALL)
        current += 210


def header(draw: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    text(draw, (70, 45), title, TITLE)
    text(draw, (72, 102), subtitle, SUBTITLE, "#475569")


def load_data() -> dict[str, list[dict]]:
    return {
        "dataset": read_csv(BENCHMARK_DIR / "dataset_summary.csv"),
        "comparison": read_csv(BENCHMARK_DIR / "results" / "comparison_overall.csv"),
        "by_type": read_csv(BENCHMARK_DIR / "results" / "comparison_by_type.csv"),
        "field_metrics": read_csv(BENCHMARK_DIR / "metrics_doctr_improved2" / "field_metrics.csv"),
        "mismatches": read_csv(BENCHMARK_DIR / "metrics_doctr_improved2" / "field_mismatches.csv"),
        "improvement": read_csv(BENCHMARK_DIR / "results" / "extraction_improvement_by_type.csv"),
        "preprocess": read_csv(BENCHMARK_DIR / "results" / "preprocessing_ablation_overall.csv"),
    }


def plot_dataset_dashboard(data: dict[str, list[dict]]) -> None:
    image, draw = canvas(1700, 1050)
    header(draw, "EnglishCert-110 Benchmark Dataset", "Composition, annotation volume, and file formats used for evaluation")

    rows = [r for r in data["dataset"] if r["cert_type"] != "TOTAL"]
    total_samples = sum(int(r["samples"]) for r in rows)
    total_fields = sum(int(r["field_annotation_rows"]) for r in rows)
    total_files = sum(int(r["jpg"]) + int(r["jpeg"]) + int(r["png"]) + int(r["pdf"]) for r in rows)

    cards = [
        ("Documents", f"{total_samples}", "certificate images"),
        ("Field labels", f"{total_fields}", "manual annotations"),
        ("Certificate types", "4", "IELTS, TOEIC, TOEFL, Cambridge"),
        ("Image files", f"{total_files}", "JPG / JPEG / PNG"),
    ]
    x = 70
    for title, value, note in cards:
        rounded(draw, (x, 160, x + 360, 300), "#FFFFFF")
        text(draw, (x + 28, 184), title, SMALL_BOLD, "#475569")
        text(draw, (x + 28, 216), value, font(44, True), "#0F172A")
        text(draw, (x + 28, 270), note, SMALL, "#64748B")
        x += 390

    rounded(draw, (70, 340, 840, 950), "#FFFFFF")
    text(draw, (105, 375), "Sample Distribution", H2)
    center = (350, 650)
    radius = 205
    start = -90
    for row in rows:
        angle = int(360 * int(row["samples"]) / total_samples)
        draw.pieslice(
            (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
            start,
            start + angle,
            fill=CERT_COLORS[row["cert_type"]],
        )
        start += angle
    draw.ellipse((center[0] - 95, center[1] - 95, center[0] + 95, center[1] + 95), fill="#FFFFFF")
    centered_text(draw, (center[0] - 90, center[1] - 65, center[0] + 90, center[1] + 65), "110\nsamples", font(34, True))

    y = 455
    for row in rows:
        cert = row["cert_type"]
        count = int(row["samples"])
        draw.rounded_rectangle((595, y + 4, 625, y + 26), radius=6, fill=CERT_COLORS[cert])
        text(draw, (640, y + 2), cert, SMALL_BOLD)
        text(draw, (755, y), f"{count} ({count / total_samples * 100:.1f}%)", SMALL, "#475569")
        y += 68

    rounded(draw, (880, 340, 1630, 950), "#FFFFFF")
    text(draw, (915, 375), "Annotation Rows by Certificate Type", H2)
    max_fields = max(int(r["field_annotation_rows"]) for r in rows)
    y = 470
    for row in rows:
        cert = row["cert_type"]
        fields = int(row["field_annotation_rows"])
        samples = int(row["samples"])
        bar_w = int(500 * fields / max_fields)
        text(draw, (925, y), cert, BODY_BOLD)
        draw.rounded_rectangle((1100, y + 2, 1600, y + 32), radius=12, fill="#E2E8F0")
        draw.rounded_rectangle((1100, y + 2, 1100 + bar_w, y + 32), radius=12, fill=CERT_COLORS[cert])
        text(draw, (1100 + bar_w + 14, y), f"{fields}", BODY_BOLD, "#0F172A")
        text(draw, (925, y + 36), f"{samples} docs x {row['fields_per_sample']} fields", SMALL, "#64748B")
        y += 105

    text(draw, (915, 890), "Report use: Chapter 3 dataset description and Chapter 6 benchmark setup.", SMALL, "#64748B")
    save(image, "01_dataset_dashboard.png")


def plot_engine_scorecards(data: dict[str, list[dict]]) -> None:
    image, draw = canvas(1700, 1000)
    header(draw, "Zero-shot OCR Engine Scorecards", "Same dataset, same extraction pipeline, different OCR backbones")
    rows = [r for r in data["comparison"] if r["config"] in OCR_ORDER]
    rows = sorted(rows, key=lambda r: OCR_ORDER.index(r["config"]))

    best_acc = max(float(r["field_normalized_accuracy"]) for r in rows)
    best_time = min(float(r["avg_processing_ms"]) for r in rows)
    x = 90
    for idx, row in enumerate(rows, start=1):
        config = row["config"]
        acc = float(row["field_normalized_accuracy"])
        cls = float(row["classification_accuracy"])
        seconds = float(row["avg_processing_ms"]) / 1000
        color = ENGINE_COLORS[config]
        rounded(draw, (x, 190, x + 480, 800), "#FFFFFF", radius=30)
        draw.rounded_rectangle((x, 190, x + 480, 310), radius=30, fill=color)
        text(draw, (x + 35, 225), OCR_LABELS[config], font(38, True), "#FFFFFF")
        text(draw, (x + 35, 272), f"Rank #{idx}", BODY_BOLD, "#E0F2FE")

        text(draw, (x + 35, 360), "Field accuracy", SMALL_BOLD, "#64748B")
        text(draw, (x + 35, 392), pct(acc, 2), font(52, True), "#0F172A")
        if acc == best_acc:
            draw.rounded_rectangle((x + 275, 405, x + 420, 442), radius=16, fill="#DBEAFE")
            centered_text(draw, (x + 275, 405, x + 420, 442), "best acc.", SMALL_BOLD, "#1D4ED8")

        text(draw, (x + 35, 505), "Classification accuracy", SMALL_BOLD, "#64748B")
        text(draw, (x + 35, 536), pct(cls, 2), font(36, True), "#0F172A")

        text(draw, (x + 35, 620), "Average runtime", SMALL_BOLD, "#64748B")
        text(draw, (x + 35, 651), f"{seconds:.2f}s", font(36, True), "#0F172A")
        if float(row["avg_processing_ms"]) == best_time:
            draw.rounded_rectangle((x + 250, 662, x + 405, 699), radius=16, fill="#CCFBF1")
            centered_text(draw, (x + 250, 662, x + 405, 699), "fastest", SMALL_BOLD, "#0F766E")

        bar_y = 735
        draw.rounded_rectangle((x + 35, bar_y, x + 445, bar_y + 18), radius=9, fill="#E2E8F0")
        draw.rounded_rectangle((x + 35, bar_y, x + 35 + int(410 * acc), bar_y + 18), radius=9, fill=color)
        x += 535

    text(draw, (90, 885), "Interpretation: docTR gives the best extraction accuracy; PaddleOCR provides a strong speed/accuracy trade-off; EasyOCR is a weak zero-shot baseline on this dataset.", BODY, "#334155")
    save(image, "02_ocr_engine_scorecards.png")


def plot_tradeoff(data: dict[str, list[dict]]) -> None:
    image, draw = canvas(1700, 1050)
    header(draw, "Accuracy vs. Runtime Trade-off", "Field-level accuracy and average processing time on EnglishCert-110")
    rows = [r for r in data["comparison"] if r["config"] in OCR_ORDER]

    plot = (145, 190, 1510, 850)
    x1, y1, x2, y2 = plot
    rounded(draw, (70, 150, 1630, 940), "#FFFFFF")
    draw.rectangle(plot, fill="#FFFFFF")
    draw.rounded_rectangle((x1, y1, x2, y2), radius=16, outline="#CBD5E1", width=2)

    times = [float(r["avg_processing_ms"]) / 1000 for r in rows]
    accs = [float(r["field_normalized_accuracy"]) * 100 for r in rows]
    min_x, max_x = max(0, min(times) - 1), max(times) + 1
    min_y, max_y = max(0, min(accs) - 10), min(100, max(accs) + 5)

    for i in range(6):
        gx = x1 + (x2 - x1) * i / 5
        gy = y2 - (y2 - y1) * i / 5
        draw.line((gx, y1, gx, y2), fill="#E2E8F0", width=1)
        draw.line((x1, gy, x2, gy), fill="#E2E8F0", width=1)
        text(draw, (gx - 22, y2 + 20), f"{min_x + (max_x - min_x) * i / 5:.1f}", SMALL, "#64748B")
        text(draw, (82, gy - 11), f"{min_y + (max_y - min_y) * i / 5:.0f}", SMALL, "#64748B")

    text(draw, ((x1 + x2) // 2 - 90, 900), "Average processing time (seconds, lower is better)", BODY_BOLD, "#334155")
    text(draw, (45, 505), "Field accuracy (%)", BODY_BOLD, "#334155")
    draw.polygon([(x1 + 12, y1 + 12), (x1 + 310, y1 + 12), (x1 + 12, y1 + 180)], fill="#ECFDF5")
    text(draw, (x1 + 30, y1 + 28), "desirable region", SMALL_BOLD, "#047857")
    text(draw, (x1 + 30, y1 + 55), "higher accuracy\nlower runtime", TINY, "#047857")

    for row in rows:
        config = row["config"]
        seconds = float(row["avg_processing_ms"]) / 1000
        acc = float(row["field_normalized_accuracy"]) * 100
        px = x1 + (seconds - min_x) / (max_x - min_x) * (x2 - x1)
        py = y2 - (acc - min_y) / (max_y - min_y) * (y2 - y1)
        color = ENGINE_COLORS[config]
        draw.ellipse((px - 30, py - 30, px + 30, py + 30), fill=color, outline="#FFFFFF", width=5)
        text(draw, (int(px + 42), int(py - 34)), OCR_LABELS[config], BODY_BOLD)
        text(draw, (int(px + 42), int(py - 4)), f"{acc:.1f}% / {seconds:.2f}s", SMALL, "#475569")

    text(draw, (115, 955), "Report use: justifies OCR selection as an accuracy-runtime decision instead of an arbitrary choice.", BODY, "#475569")
    save(image, "03_ocr_accuracy_runtime_tradeoff.png")


def plot_heatmap(data: dict[str, list[dict]], metric: str, name: str, title: str, subtitle: str, lower_is_better: bool = False) -> None:
    image, draw = canvas(1700, 1000)
    header(draw, title, subtitle)
    rows = [r for r in data["by_type"] if r["config"] in OCR_ORDER]
    values = {(r["config"], r["cert_type"]): float(r[metric]) for r in rows}
    if metric == "avg_processing_ms":
        values = {k: v / 1000 for k, v in values.items()}
    all_values = list(values.values())
    min_v, max_v = min(all_values), max(all_values)

    left, top = 300, 220
    cell_w, cell_h = 290, 145
    rounded(draw, (100, 170, 1600, 870), "#FFFFFF")

    for c_idx, cert in enumerate(CERT_ORDER):
        centered_text(draw, (left + c_idx * cell_w, top - 58, left + (c_idx + 1) * cell_w, top - 10), cert, BODY_BOLD, "#0F172A")
    for r_idx, config in enumerate(OCR_ORDER):
        centered_text(draw, (120, top + r_idx * cell_h, left - 35, top + (r_idx + 1) * cell_h), OCR_LABELS[config], BODY_BOLD, "#0F172A")
        for c_idx, cert in enumerate(CERT_ORDER):
            value = values[(config, cert)]
            if lower_is_better:
                fill = runtime_color(value, min_v, max_v)
                label = f"{value:.2f}s"
            else:
                fill = quality_color(value)
                label = f"{value * 100:.1f}%"
            box = (
                left + c_idx * cell_w + 8,
                top + r_idx * cell_h + 8,
                left + (c_idx + 1) * cell_w - 8,
                top + (r_idx + 1) * cell_h - 8,
            )
            rounded(draw, box, fill, outline="#FFFFFF", radius=18, width=3)
            centered_text(draw, box, label, font(32, True), "#0F172A")

    if lower_is_better:
        legend(draw, [("faster", "#DCFCE7"), ("slower", "#FDBA74")], 610, 795)
    else:
        legend(draw, [("weak", "#FB923C"), ("moderate", "#FDE68A"), ("strong", "#22C55E")], 510, 795)
    save(image, name)


def short_field(key: str) -> str:
    mapping = {
        "candidate.full_name": "name",
        "candidate.id": "id",
        "candidate.test_date": "test date",
        "candidate.birth_date": "birth date",
        "certificate.number": "cert no.",
        "score.listening": "listen",
        "score.reading": "read",
        "score.writing": "write",
        "score.speaking": "speak",
        "score.overall": "overall",
        "score.total": "total",
        "cefr.level": "CEFR",
    }
    return mapping.get(key, key.replace("candidate.", "").replace("score.", ""))


def plot_field_heatmap(data: dict[str, list[dict]]) -> None:
    image, draw = canvas(1900, 1150)
    header(draw, "docTR Field-level Accuracy Heatmap", "Normalized extraction accuracy per target field after rule improvements")
    rows = data["field_metrics"]
    fields = sorted({r["field_key"] for r in rows})
    values = {(r["cert_type"], r["field_key"]): float(r["normalized_accuracy"]) for r in rows}

    left, top = 260, 210
    cell_w, cell_h = 92, 135
    rounded(draw, (70, 155, 1830, 1040), "#FFFFFF")

    for idx, field in enumerate(fields):
        label = short_field(field)
        x = left + idx * cell_w + cell_w / 2
        draw.text((x, top - 20), label, font=TINY, fill="#334155", anchor="rs")

    for r_idx, cert in enumerate(CERT_ORDER):
        centered_text(draw, (95, top + r_idx * cell_h, left - 20, top + (r_idx + 1) * cell_h), cert, BODY_BOLD)
        for c_idx, field in enumerate(fields):
            box = (
                left + c_idx * cell_w + 4,
                top + r_idx * cell_h + 10,
                left + (c_idx + 1) * cell_w - 4,
                top + (r_idx + 1) * cell_h - 10,
            )
            if (cert, field) not in values:
                rounded(draw, box, "#F1F5F9", outline="#FFFFFF", radius=12)
                centered_text(draw, box, "-", SMALL, "#94A3B8")
                continue
            value = values[(cert, field)]
            rounded(draw, box, quality_color(value), outline="#FFFFFF", radius=12, width=2)
            centered_text(draw, box, f"{value * 100:.0f}", SMALL_BOLD)

    text(draw, (260, 1010), "Cells show normalized accuracy (%). Blank cells mean the field is not part of that certificate schema.", SMALL, "#64748B")
    legend(draw, [("weak", "#FB923C"), ("moderate", "#FDE68A"), ("strong", "#22C55E")], 1090, 1008)
    save(image, "06_doctr_field_accuracy_heatmap.png")


def plot_error_taxonomy(data: dict[str, list[dict]]) -> None:
    image, draw = canvas(1700, 1000)
    header(draw, "docTR Error Taxonomy", "Where the remaining field-level mismatches come from")
    mismatches = data["mismatches"]
    reason_counts = Counter(r["reason"] for r in mismatches)
    type_counts = Counter(r["expected_type"] for r in mismatches)
    total = sum(reason_counts.values())
    colors = ["#2563EB", "#14B8A6", "#F97316", "#EF4444", "#8B5CF6", "#64748B"]

    rounded(draw, (70, 160, 820, 900), "#FFFFFF")
    text(draw, (105, 200), "Mismatch Reasons", H2)
    center, radius = (355, 545), 220
    start = -90
    for idx, (reason, count) in enumerate(reason_counts.most_common()):
        angle = 360 * count / total
        draw.pieslice((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), start, start + angle, fill=colors[idx % len(colors)])
        start += angle
    draw.ellipse((center[0] - 95, center[1] - 95, center[0] + 95, center[1] + 95), fill="#FFFFFF")
    centered_text(draw, (center[0] - 80, center[1] - 60, center[0] + 80, center[1] + 60), f"{total}\nerrors", font(32, True))
    y = 750
    x = 110
    for idx, (reason, count) in enumerate(reason_counts.most_common()):
        draw.rounded_rectangle((x, y, x + 28, y + 18), radius=5, fill=colors[idx % len(colors)])
        text(draw, (x + 38, y - 5), f"{reason.replace('_', ' ')}: {count}", SMALL)
        y += 32
        if y > 870:
            y = 750
            x += 330

    rounded(draw, (870, 160, 1630, 900), "#FFFFFF")
    text(draw, (905, 200), "Mismatches by Certificate Type", H2)
    max_count = max(type_counts.values())
    y = 310
    for cert in CERT_ORDER:
        count = type_counts[cert]
        bar_w = int(560 * count / max_count)
        text(draw, (920, y), cert, BODY_BOLD)
        draw.rounded_rectangle((1080, y + 2, 1580, y + 36), radius=14, fill="#E2E8F0")
        draw.rounded_rectangle((1080, y + 2, 1080 + bar_w, y + 36), radius=14, fill=CERT_COLORS[cert])
        text(draw, (1092 + bar_w, y + 3), f"{count}", BODY_BOLD)
        y += 115
    text(draw, (905, 820), "Report use: supports qualitative error analysis instead of only reporting aggregate accuracy.", SMALL, "#64748B")
    save(image, "07_doctr_error_taxonomy.png")


def plot_preprocess_and_improvement(data: dict[str, list[dict]]) -> None:
    image, draw = canvas(1700, 1000)
    header(draw, "Ablation Study Summary", "Effect of preprocessing and extraction-rule refinement")

    rounded(draw, (70, 160, 800, 900), "#FFFFFF")
    text(draw, (105, 205), "Preprocessing Ablation", H2)
    pre = {r["config"]: r for r in data["preprocess"]}
    full = float(pre["docTR_full_improved"]["field_normalized_accuracy"]) * 100
    none = float(pre["docTR_no_preprocessing"]["field_normalized_accuracy"]) * 100
    full_t = float(pre["docTR_full_improved"]["avg_processing_ms"]) / 1000
    none_t = float(pre["docTR_no_preprocessing"]["avg_processing_ms"]) / 1000
    x0, x1 = 200, 650
    for y, label, v0, v1, suffix in [
        (385, "Field accuracy", none, full, "%"),
        (590, "Runtime", none_t, full_t, "s"),
    ]:
        text(draw, (105, y - 75), label, BODY_BOLD, "#334155")
        draw.line((x0, y, x1, y), fill="#CBD5E1", width=5)
        draw.ellipse((x0 - 20, y - 20, x0 + 20, y + 20), fill="#64748B")
        draw.ellipse((x1 - 20, y - 20, x1 + 20, y + 20), fill="#2563EB")
        centered_text(draw, (x0 - 80, y + 34, x0 + 80, y + 90), f"no-prep\n{v0:.2f}{suffix}", SMALL_BOLD)
        centered_text(draw, (x1 - 80, y + 34, x1 + 80, y + 90), f"full\n{v1:.2f}{suffix}", SMALL_BOLD)
    text(draw, (105, 790), "Finding: preprocessing gives a small accuracy gain on this clean benchmark, but remains important for real-world noisy scans.", SMALL, "#475569")

    rounded(draw, (850, 160, 1630, 900), "#FFFFFF")
    text(draw, (885, 205), "Extraction-rule Improvement", H2)
    improvement = data["improvement"]
    y = 320
    for row in improvement:
        cert = row["cert_type"]
        base = float(row["baseline_normalized_accuracy"]) * 100
        improved = float(row["improved_normalized_accuracy"]) * 100
        delta = improved - base
        text(draw, (900, y), cert, BODY_BOLD)
        scale_min, scale_max = 70, 100
        bx = 1080 + int((base - scale_min) / (scale_max - scale_min) * 430)
        ix = 1080 + int((improved - scale_min) / (scale_max - scale_min) * 430)
        draw.line((1080, y + 14, 1510, y + 14), fill="#E2E8F0", width=4)
        draw.ellipse((bx - 13, y + 1, bx + 13, y + 27), fill="#94A3B8")
        draw.ellipse((ix - 15, y - 1, ix + 15, y + 29), fill=CERT_COLORS.get(cert, "#2563EB"))
        text(draw, (1530, y - 5), f"{delta:+.1f} pp", BODY_BOLD, "#0F172A")
        y += 115
    text(draw, (1080, 805), "70%", SMALL, "#64748B")
    text(draw, (1480, 805), "100%", SMALL, "#64748B")
    save(image, "08_ablation_and_rule_improvement.png")


def plot_missing_field_burden(data: dict[str, list[dict]]) -> None:
    image, draw = canvas(1700, 950)
    header(draw, "Missing Prediction Burden", "How many annotated fields were not extracted by each OCR configuration")
    rows = [r for r in data["by_type"] if r["config"] in OCR_ORDER]
    by_config = defaultdict(dict)
    for row in rows:
        by_config[row["config"]][row["cert_type"]] = int(row["missing_predictions"])

    rounded(draw, (70, 160, 1630, 830), "#FFFFFF")
    left, top = 330, 285
    max_total = max(sum(by_config[c].values()) for c in OCR_ORDER)
    bar_w = 980
    for idx, config in enumerate(OCR_ORDER):
        total = sum(by_config[config].values())
        y = top + idx * 160
        text(draw, (120, y + 18), OCR_LABELS[config], H2)
        draw.rounded_rectangle((left, y + 18, left + bar_w, y + 72), radius=22, fill="#E2E8F0")
        offset = 0
        for cert in CERT_ORDER:
            value = by_config[config].get(cert, 0)
            seg_w = int(bar_w * value / max_total) if max_total else 0
            if seg_w <= 0:
                continue
            draw.rounded_rectangle((left + offset, y + 18, left + offset + seg_w, y + 72), radius=22, fill=CERT_COLORS[cert])
            if seg_w > 52:
                centered_text(draw, (left + offset, y + 18, left + offset + seg_w, y + 72), str(value), SMALL_BOLD, "#FFFFFF")
            offset += seg_w
        text(draw, (left + bar_w + 35, y + 18), f"{total}", font(34, True))
        text(draw, (left + bar_w + 35, y + 58), "missing fields", SMALL, "#64748B")
        text(draw, (left + bar_w + 35, y + 88), f"{total / 1030 * 100:.1f}% of annotations", SMALL, "#64748B")

    for i in range(6):
        x = left + bar_w * i / 5
        draw.line((x, top - 30, x, top + 390), fill="#F1F5F9", width=1)
        text(draw, (x - 10, top + 420), f"{int(max_total * i / 5)}", SMALL, "#64748B")
    text(draw, (left + 360, top + 452), "Missing field count", BODY_BOLD, "#334155")

    legend(draw, [(cert, CERT_COLORS[cert]) for cert in CERT_ORDER], 430, 760)
    text(draw, (120, 875), "Report use: complements accuracy with a reliability view: missed fields usually trigger manual review in the human-in-the-loop interface.", BODY, "#475569")
    save(image, "09_missing_prediction_burden.png")


def build_catalog() -> None:
    lines = [
        "# Research Figure Catalog",
        "",
        "Use these figures for the experiments, dataset, and discussion chapters.",
        "",
        "| File | Best report section | Why it is useful |",
        "| --- | --- | --- |",
        "| `01_dataset_dashboard.png` | Dataset / Benchmark setup | Shows sample distribution, field-label volume, and file formats in one figure. |",
        "| `02_ocr_engine_scorecards.png` | OCR comparison | Gives a compact headline result for each OCR engine. |",
        "| `03_ocr_accuracy_runtime_tradeoff.png` | OCR model selection | Justifies choosing docTR through an accuracy-runtime trade-off, not intuition. |",
        "| `04_ocr_accuracy_heatmap.png` | Per-type OCR analysis | Shows which OCR engine works best for each certificate type. |",
        "| `05_ocr_runtime_heatmap.png` | Runtime analysis | Shows processing-time differences by certificate type. |",
        "| `06_doctr_field_accuracy_heatmap.png` | Field-level evaluation | Exposes which schema fields are reliable and which remain difficult. |",
        "| `07_doctr_error_taxonomy.png` | Error analysis | Groups mismatches by reason and certificate type. |",
        "| `08_ablation_and_rule_improvement.png` | Ablation study | Summarizes preprocessing and extraction-rule improvements. |",
        "| `09_missing_prediction_burden.png` | Human-in-the-loop motivation | Shows why review/editing remains necessary for reliability. |",
        "",
    ]
    write_text(ASSET_DIR / "RESEARCH_FIGURE_CATALOG.md", "\n".join(lines))


def main() -> int:
    data = load_data()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plot_dataset_dashboard(data)
    plot_engine_scorecards(data)
    plot_tradeoff(data)
    plot_heatmap(
        data,
        "field_normalized_accuracy",
        "04_ocr_accuracy_heatmap.png",
        "OCR Accuracy Heatmap",
        "Normalized field accuracy by engine and certificate type",
        lower_is_better=False,
    )
    plot_heatmap(
        data,
        "avg_processing_ms",
        "05_ocr_runtime_heatmap.png",
        "OCR Runtime Heatmap",
        "Average processing time by engine and certificate type",
        lower_is_better=True,
    )
    plot_field_heatmap(data)
    plot_error_taxonomy(data)
    plot_preprocess_and_improvement(data)
    plot_missing_field_burden(data)
    build_catalog()
    print(f"Wrote research figures to {FIGURE_DIR}")
    print(f"Wrote figure catalog to {ASSET_DIR / 'RESEARCH_FIGURE_CATALOG.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
