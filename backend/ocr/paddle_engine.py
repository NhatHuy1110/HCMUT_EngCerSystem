import os
import tempfile
import threading
from pathlib import Path

import cv2

from .base import BaseOCREngine, OCRPage, OCRWord


_ocr = None
_ocr_lock = threading.Lock()


def _get_ocr():
    global _ocr
    with _ocr_lock:
        if _ocr is None:
            # PaddlePaddle can collide with other OpenMP-backed libraries in the
            # same Windows venv. This is scoped to the process that runs OCR.
            # Paddle Inference is sensitive to non-ASCII model paths on Windows,
            # so keep its downloaded weights in an ASCII temp directory instead
            # of the project folder whose parent path contains Vietnamese text.
            cache_dir = Path(tempfile.gettempdir()) / "englishcer_paddle_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache_dir))
            os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

            from paddleocr import PaddleOCR

            _ocr = PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="en_PP-OCRv5_mobile_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
    return _ocr


def _box_to_bbox(box, width: int, height: int) -> list[int]:
    try:
        values = box.tolist()
    except AttributeError:
        values = box

    if values and isinstance(values[0], (list, tuple)):
        xs = [float(point[0]) for point in values]
        ys = [float(point[1]) for point in values]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    else:
        flat = [float(v) for v in values]
        if len(flat) >= 4:
            x1, y1, x2, y2 = flat[:4]
        else:
            x1 = y1 = x2 = y2 = 0

    return [
        max(0, int(x1)),
        max(0, int(y1)),
        min(width, int(x2)),
        min(height, int(y2)),
    ]


class PaddleOCREngine(BaseOCREngine):
    name = "paddleocr"

    def recognize(self, image_bgr) -> OCRPage:
        h, w = image_bgr.shape[:2]
        ocr = _get_ocr()

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            cv2.imwrite(tmp_path, image_bgr)
            results = ocr.predict(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        words: list[OCRWord] = []
        for result in results:
            texts = result.get("rec_texts", []) if hasattr(result, "get") else result["rec_texts"]
            scores = result.get("rec_scores", []) if hasattr(result, "get") else result["rec_scores"]
            boxes = result.get("rec_boxes", []) if hasattr(result, "get") else result["rec_boxes"]
            for text, score, box in zip(texts, scores, boxes):
                text = str(text or "").strip()
                if not text:
                    continue
                words.append(
                    OCRWord(
                        text=text,
                        confidence=float(score or 0.0),
                        bbox=_box_to_bbox(box, w, h),
                    )
                )

        return OCRPage(width=w, height=h, engine=self.name, words=words)
