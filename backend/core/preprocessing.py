from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np


@dataclass
class PreprocessResult:
    image_bgr: np.ndarray
    original_width: int
    original_height: int
    warnings: list[str]


def decode_image(file_bytes: bytes, filename: str = "") -> np.ndarray:
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        try:
            import pypdfium2 as pdfium
        except Exception as exc:
            raise ValueError("PDF upload requires pypdfium2. Please install backend requirements.") from exc

        pdf = pdfium.PdfDocument(BytesIO(file_bytes))
        if len(pdf) == 0:
            raise ValueError("PDF has no pages")
        page = pdf[0]
        bitmap = page.render(scale=2.5)
        pil_image = bitmap.to_pil().convert("RGB")
        rgb = np.array(pil_image)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    data = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Cannot decode image bytes")
    return img


def _auto_crop_borders(img_bgr: np.ndarray, threshold: int = 246, pad: int = 12) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    mask = gray < threshold
    coords = np.column_stack(np.where(mask))
    if coords.size == 0:
        return img_bgr
    y1, x1 = coords.min(axis=0)
    y2, x2 = coords.max(axis=0) + 1
    y1 = max(0, y1 - pad)
    x1 = max(0, x1 - pad)
    y2 = min(img_bgr.shape[0], y2 + pad)
    x2 = min(img_bgr.shape[1], x2 + pad)
    return img_bgr[y1:y2, x1:x2]


def _deskew_hough(img_bgr: np.ndarray) -> tuple[np.ndarray, float]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 140)
    angle = 0.0

    if lines is not None:
        angles = []
        for rho, theta in lines[:, 0]:
            deg = theta * 180 / np.pi
            if deg < 12 or deg > 168:
                if deg > 90:
                    deg -= 180
                angles.append(deg)
        if angles:
            angle = float(np.median(angles))

    if abs(angle) < 0.25:
        return img_bgr, 0.0

    h, w = img_bgr.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        img_bgr,
        matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, angle


def preprocess_image(img_bgr: np.ndarray, max_side: int = 2200) -> PreprocessResult:
    warnings: list[str] = []
    original_height, original_width = img_bgr.shape[:2]

    img = _auto_crop_borders(img_bgr)
    img, angle = _deskew_hough(img)
    if abs(angle) >= 0.25:
        warnings.append(f"deskew_angle={angle:.2f}")

    h, w = img.shape[:2]
    largest = max(h, w)
    if largest > max_side:
        scale = max_side / largest
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        warnings.append(f"resized_to_max_side={max_side}")

    return PreprocessResult(
        image_bgr=img,
        original_width=original_width,
        original_height=original_height,
        warnings=warnings,
    )
