from dataclasses import dataclass, field
from typing import Any


@dataclass
class OCRWord:
    text: str
    confidence: float
    bbox: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(float(self.confidence or 0.0), 4),
            "bbox": [int(v) for v in self.bbox],
        }


@dataclass
class OCRPage:
    width: int
    height: int
    engine: str
    words: list[OCRWord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def plain_text(self) -> str:
        return " ".join(w.text for w in self.words if w.text).strip()

    def mean_confidence(self) -> float:
        if not self.words:
            return 0.0
        return sum(float(w.confidence or 0.0) for w in self.words) / len(self.words)

    def to_dict(self, limit_words: int = 500) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "width": self.width,
            "height": self.height,
            "word_count": len(self.words),
            "mean_confidence": round(self.mean_confidence(), 4),
            "warnings": self.warnings,
            "words": [w.to_dict() for w in self.words[:limit_words]],
            "text_preview": self.plain_text()[:2000],
        }


class BaseOCREngine:
    name = "base"

    def recognize(self, image_bgr) -> OCRPage:
        raise NotImplementedError


class EmptyOCREngine(BaseOCREngine):
    name = "empty"

    def __init__(self, reason: str):
        self.reason = reason

    def recognize(self, image_bgr) -> OCRPage:
        h, w = image_bgr.shape[:2]
        return OCRPage(
            width=w,
            height=h,
            engine=self.name,
            words=[],
            warnings=[self.reason],
        )
