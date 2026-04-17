import re
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    cert_type: str
    confidence: float
    scores: dict[str, float]
    evidence: dict[str, list[str]]

    def to_dict(self) -> dict:
        return {
            "cert_type": self.cert_type,
            "confidence": round(self.confidence, 4),
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "evidence": self.evidence,
        }


PROFILES = {
    "IELTS": [
        r"\bIELTS\b",
        r"International English Language Testing System",
        r"Test Report Form",
        r"Overall Band Score",
        r"British Council",
        r"\bIDP\b",
    ],
    "TOEIC": [
        r"\bTOEIC\b",
        r"Test of English for International Communication",
        r"Listening and Reading",
        r"Official Score",
        r"Institutional Score",
        r"\bETS\b",
    ],
    "TOEFL": [
        r"\bTOEFL\b",
        r"Test of English as a Foreign Language",
        r"\biBT\b",
        r"Test Taker Score Report",
        r"\bETS\b",
    ],
    "Cambridge": [
        r"\bCambridge\b",
        r"Cambridge Assessment English",
        r"University of Cambridge",
        r"Language Assessment",
        r"\bFCE\b|\bCAE\b|\bPET\b|\bKET\b|\bB1\b|\bB2\b|\bC1\b|\bC2\b",
    ],
}


def classify_certificate(text: str, width: int, height: int) -> ClassificationResult:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}

    for cert_type, patterns in PROFILES.items():
        hits = []
        score = 0.0
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.I)
            if match:
                hits.append(match.group(0))
                score += 1.0
        scores[cert_type] = score
        evidence[cert_type] = hits

    # IELTS certificates often contain the Cambridge Assessment English logo,
    # so explicit IELTS/TRF language must outrank that publisher mark.
    if re.search(r"\bIELTS\b|Test Report Form|Overall Band Score", normalized, flags=re.I):
        scores["IELTS"] = scores.get("IELTS", 0.0) + 3.0
        evidence["IELTS"].append("ielts_priority_signal")
        if not re.search(r"Statement of Results|Certificate in|First Certificate|Advanced|Preliminary", normalized, flags=re.I):
            scores["Cambridge"] = max(0.0, scores.get("Cambridge", 0.0) - 2.0)

    if re.search(r"\bTOEIC\b|Listening and Reading|Official Score", normalized, flags=re.I):
        scores["TOEIC"] = scores.get("TOEIC", 0.0) + 2.0
        evidence["TOEIC"].append("toeic_priority_signal")
        if not re.search(r"\bTOEFL\b|iBT|Test Taker Score Report", normalized, flags=re.I):
            scores["TOEFL"] = max(0.0, scores.get("TOEFL", 0.0) - 0.8)

    if width > height * 1.25:
        scores["TOEIC"] = scores.get("TOEIC", 0.0) + 0.6
        evidence["TOEIC"].append("landscape_layout")

    total = sum(scores.values())
    if total <= 0:
        return ClassificationResult("Unknown", 0.0, scores, evidence)

    cert_type = max(scores, key=scores.get)
    confidence = scores[cert_type] / total
    return ClassificationResult(cert_type, float(confidence), scores, evidence)
