import os
import tempfile
import threading
from pathlib import Path

import cv2

from .base import BaseOCREngine, OCRPage, OCRWord


_predictor = None
_predictor_lock = threading.Lock()


def _get_predictor():
    global _predictor
    with _predictor_lock:
        if _predictor is None:
            from doctr.models import ocr_predictor

            project_root = Path(__file__).resolve().parents[2]
            cache_dir = project_root / ".cache" / "doctr"
            cache_dir.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("DOCTR_CACHE_DIR", str(cache_dir))
            os.environ.setdefault("DOCTR_MULTIPROCESSING_DISABLE", "TRUE")

            _predictor = ocr_predictor(
                det_arch="db_resnet50",
                reco_arch="crnn_vgg16_bn",
                pretrained=True,
            )
    return _predictor


class DocTREngine(BaseOCREngine):
    name = "doctr"

    def recognize(self, image_bgr) -> OCRPage:
        from doctr.io import DocumentFile

        h, w = image_bgr.shape[:2]
        predictor = _get_predictor()

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            cv2.imwrite(tmp_path, image_bgr)
            doc = DocumentFile.from_images(tmp_path)
            exported = predictor(doc).export()
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        words: list[OCRWord] = []
        for page in exported.get("pages", []):
            for block in page.get("blocks", []):
                for line in block.get("lines", []):
                    for word in line.get("words", []):
                        text = str(word.get("value", "")).strip()
                        if not text:
                            continue
                        geom = word.get("geometry") or ((0, 0), (0, 0))
                        (x1, y1), (x2, y2) = geom
                        bbox = [
                            max(0, int(x1 * w)),
                            max(0, int(y1 * h)),
                            min(w, int(x2 * w)),
                            min(h, int(y2 * h)),
                        ]
                        words.append(
                            OCRWord(
                                text=text,
                                confidence=float(word.get("confidence") or 0.0),
                                bbox=bbox,
                            )
                        )

        return OCRPage(width=w, height=h, engine=self.name, words=words)
