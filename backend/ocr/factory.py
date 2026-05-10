import os
from importlib.util import find_spec

from .base import BaseOCREngine, EmptyOCREngine


def get_ocr_engine(preferred: str | None = None) -> BaseOCREngine:
    requested = (preferred or os.getenv("OCR_ENGINE") or "doctr").strip().lower()
    order = ["doctr", "paddleocr", "easyocr"] if requested == "auto" else [requested, "doctr", "paddleocr", "easyocr"]

    errors: list[str] = []
    for name in dict.fromkeys(order):
        try:
            if name == "doctr":
                if find_spec("doctr") is None:
                    errors.append("doctr: python-doctr is not installed in this environment")
                    continue
                from .doctr_engine import DocTREngine

                return DocTREngine()
            if name == "easyocr":
                if find_spec("easyocr") is None:
                    errors.append("easyocr: easyocr is not installed in this environment")
                    continue
                from .easyocr_engine import EasyOCREngine

                return EasyOCREngine()
            if name in {"paddleocr", "paddle"}:
                if find_spec("paddleocr") is None:
                    errors.append("paddleocr: paddleocr is not installed in this environment")
                    continue
                from .paddle_engine import PaddleOCREngine

                return PaddleOCREngine()
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    return EmptyOCREngine("No OCR engine could be initialized. " + " | ".join(errors))
