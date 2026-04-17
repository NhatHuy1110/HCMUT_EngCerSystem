import threading

import cv2

from .base import BaseOCREngine, OCRPage, OCRWord


_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    global _reader
    with _reader_lock:
        if _reader is None:
            import easyocr

            _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


class EasyOCREngine(BaseOCREngine):
    name = "easyocr"

    def recognize(self, image_bgr) -> OCRPage:
        h, w = image_bgr.shape[:2]
        reader = _get_reader()
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        results = reader.readtext(image_rgb, detail=1, paragraph=False)

        words: list[OCRWord] = []
        for points, text, confidence in results:
            if not str(text).strip():
                continue
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            bbox = [
                max(0, int(min(xs))),
                max(0, int(min(ys))),
                min(w, int(max(xs))),
                min(h, int(max(ys))),
            ]
            words.append(OCRWord(text=str(text).strip(), confidence=float(confidence or 0.0), bbox=bbox))

        return OCRPage(width=w, height=h, engine=self.name, words=words)
