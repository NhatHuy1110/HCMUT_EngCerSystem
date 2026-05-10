import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
OUT_DIR = BENCHMARK_DIR / "report_assets" / "figures"

COLORS = {
    "IELTS": "#2F6FDB",
    "TOEIC": "#16A34A",
    "TOEFL": "#F97316",
    "Cambridge": "#8B5CF6",
}


def read_csv(path: Path) -> list[dict]:
    for encoding in ["utf-8-sig", "utf-8", "cp1258", "cp1252"]:
        try:
            with path.open("r", newline="", encoding=encoding) as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode {path}")


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            pass
    return ImageFont.load_default()


TITLE = font(42, True)
SUBTITLE = font(22)
BODY = font(21)
BODY_BOLD = font(21, True)
SMALL = font(17)
SMALL_BOLD = font(17, True)


def draw_ring(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    outer_radius: int,
    inner_radius: int,
    values: list[tuple[str, int]],
    start_angle: int,
) -> None:
    total = sum(value for _, value in values)
    current = start_angle
    cx, cy = center
    for idx, (label, value) in enumerate(values):
        extent = 360 * value / total
        end = current + extent
        if idx == len(values) - 1:
            end = start_angle + 360
        draw.pieslice(
            (cx - outer_radius, cy - outer_radius, cx + outer_radius, cy + outer_radius),
            current,
            end,
            fill=COLORS[label],
        )
        current = end
    draw.ellipse(
        (cx - inner_radius, cy - inner_radius, cx + inner_radius, cy + inner_radius),
        fill="#FFFFFF",
    )


def draw_center_label(draw: ImageDraw.ImageDraw, center: tuple[int, int], total_samples: int, total_fields: int) -> None:
    cx, cy = center
    draw.text((cx, cy - 42), "EnglishCert-110", font=font(28, True), fill="#0F172A", anchor="mm")
    draw.text((cx, cy + 2), f"{total_samples} samples", font=BODY_BOLD, fill="#2563EB", anchor="mm")
    draw.text((cx, cy + 34), f"{total_fields} field rows", font=BODY_BOLD, fill="#0F766E", anchor="mm")


def draw_legend(draw: ImageDraw.ImageDraw, rows: list[dict], total_samples: int, total_fields: int) -> None:
    x, y = 1040, 255
    draw.text((x, y - 85), "Certificate Breakdown", font=font(30, True), fill="#0F172A")
    draw.text((x, y - 48), "Outer ring: field annotations  |  Inner ring: samples", font=SMALL, fill="#64748B")

    for row in rows:
        cert = row["cert_type"]
        samples = int(row["samples"])
        fields = int(row["field_annotation_rows"])
        draw.rounded_rectangle((x, y + 6, x + 34, y + 30), radius=7, fill=COLORS[cert])
        draw.text((x + 52, y), cert, font=BODY_BOLD, fill="#0F172A")
        draw.text((x + 220, y), f"{samples} samples", font=BODY, fill="#334155")
        draw.text((x + 380, y), f"{samples / total_samples * 100:.1f}%", font=SMALL_BOLD, fill="#64748B")
        draw.text((x + 52, y + 34), f"{fields} annotated fields", font=BODY, fill="#334155")
        draw.text((x + 300, y + 34), f"{fields / total_fields * 100:.1f}% of labels", font=SMALL_BOLD, fill="#64748B")
        y += 118


def draw_ring_labels(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    rows: list[dict],
    sample_radius: int,
    field_radius: int,
) -> None:
    draw.text((center[0] - 470, center[1] - field_radius - 35), "Outer ring: annotation rows", font=SMALL_BOLD, fill="#0F766E")
    draw.text((center[0] - 430, center[1] + sample_radius + 62), "Inner ring: document samples", font=SMALL_BOLD, fill="#2563EB")

    total_samples = sum(int(row["samples"]) for row in rows)
    total_fields = sum(int(row["field_annotation_rows"]) for row in rows)
    draw.text((center[0] + 282, center[1] - 310), f"{total_fields} field rows", font=BODY_BOLD, fill="#0F766E")
    draw.text((center[0] + 170, center[1] + 252), f"{total_samples} samples", font=BODY_BOLD, fill="#2563EB")


def draw_donut_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    values: list[tuple[str, int]],
    center_label: str,
    center_note: str,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=28, fill="#FFFFFF", outline="#DDE6F3", width=1)
    draw.text((x1 + 38, y1 + 32), title, font=font(30, True), fill="#0F172A")
    draw.text((x1 + 38, y1 + 72), subtitle, font=SMALL, fill="#64748B")

    center = ((x1 + x2) // 2, y1 + 310)
    outer_radius = 210
    inner_radius = 118
    draw_ring(draw, center, outer_radius, inner_radius, values, -90)
    draw.ellipse(
        (
            center[0] - inner_radius + 4,
            center[1] - inner_radius + 4,
            center[0] + inner_radius - 4,
            center[1] + inner_radius - 4,
        ),
        fill="#FFFFFF",
    )
    draw.text((center[0], center[1] - 16), center_label, font=font(38, True), fill="#0F172A", anchor="mm")
    draw.text((center[0], center[1] + 28), center_note, font=BODY_BOLD, fill="#475569", anchor="mm")

    draw.text(
        ((x1 + x2) // 2, y2 - 44),
        "Color mapping and exact values are shown in the synchronized breakdown below.",
        font=SMALL,
        fill="#64748B",
        anchor="mm",
    )


def draw_comparison_table(draw: ImageDraw.ImageDraw, rows: list[dict], total_samples: int, total_fields: int) -> None:
    x1, y1, x2, y2 = (90, 790, 1610, 930)
    draw.rounded_rectangle((x1, y1, x2, y2), radius=24, fill="#FFFFFF", outline="#DDE6F3", width=1)
    draw.text((x1 + 34, y1 + 24), "Synchronized breakdown", font=BODY_BOLD, fill="#0F172A")

    start_x = x1 + 430
    col_w = 260
    for idx, row in enumerate(rows):
        cert = row["cert_type"]
        samples = int(row["samples"])
        fields = int(row["field_annotation_rows"])
        x = start_x + idx * col_w
        draw.rounded_rectangle((x, y1 + 28, x + 34, y1 + 52), radius=7, fill=COLORS[cert])
        draw.text((x + 46, y1 + 24), cert, font=SMALL_BOLD, fill="#0F172A")
        draw.text((x, y1 + 66), f"{samples} samples", font=SMALL, fill="#334155")
        draw.text((x + 118, y1 + 66), f"{samples / total_samples * 100:.1f}%", font=SMALL_BOLD, fill="#64748B")
        draw.text((x, y1 + 96), f"{fields} fields", font=SMALL, fill="#334155")
        draw.text((x + 118, y1 + 96), f"{fields / total_fields * 100:.1f}%", font=SMALL_BOLD, fill="#64748B")


def main() -> int:
    rows = [row for row in read_csv(BENCHMARK_DIR / "dataset_summary.csv") if row["cert_type"] != "TOTAL"]
    total_samples = sum(int(row["samples"]) for row in rows)
    total_fields = sum(int(row["field_annotation_rows"]) for row in rows)

    image = Image.new("RGB", (1700, 1000), "#F8FAFC")
    draw = ImageDraw.Draw(image)

    draw.text((70, 48), "Dataset Composition: Samples and Field Annotations", font=TITLE, fill="#0F172A")
    draw.text(
        (72, 104),
        "Two synchronized donut charts for the four supported English certificate types",
        font=SUBTITLE,
        fill="#475569",
    )

    sample_values = [(row["cert_type"], int(row["samples"])) for row in rows]
    field_values = [(row["cert_type"], int(row["field_annotation_rows"])) for row in rows]

    draw_donut_card(
        draw,
        (90, 165, 810, 760),
        "Document Samples",
        "Benchmark input distribution",
        sample_values,
        str(total_samples),
        "samples",
    )
    draw_donut_card(
        draw,
        (890, 165, 1610, 760),
        "Field Annotations",
        "Manual ground-truth labels used for evaluation",
        field_values,
        str(total_fields),
        "field rows",
    )
    draw_comparison_table(draw, rows, total_samples, total_fields)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "dataset_samples_and_fields_dual_donut.png"
    image.save(out_path)
    image.save(OUT_DIR / "dataset_samples_and_fields_twin_donuts.png")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
