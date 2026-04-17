import re
from datetime import datetime


def _parse_float(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def _looks_like_date(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    if re.search(r"\d{1,2}/[A-Z]{3,9}/\d{4}", value, flags=re.I):
        return True
    patterns = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for pattern in patterns:
        try:
            datetime.strptime(value.title(), pattern)
            return True
        except Exception:
            pass
    return bool(
        re.search(r"\d{1,2}\s+[A-Z]{3,9}\s+\d{4}", value, flags=re.I)
        or re.fullmatch(r"[A-Z]{3,9}\s+\d{4}", value, flags=re.I)
    )


def _validate_score(cert_type: str, key: str, value: str) -> list[str]:
    number = _parse_float(value)
    if number is None:
        return ["score is not numeric"]

    if cert_type == "IELTS":
        if not (0 <= number <= 9):
            return ["IELTS score must be between 0 and 9"]
        if abs(number * 2 - round(number * 2)) > 0.001:
            return ["IELTS score should use 0.5 increments"]
    elif cert_type == "TOEIC":
        max_score = 990 if key.endswith("total") else 495
        min_score = 10 if key.endswith("total") else 5
        if not (min_score <= number <= max_score):
            return [f"TOEIC score must be between {min_score} and {max_score}"]
    elif cert_type == "TOEFL":
        max_score = 120 if key.endswith("total") else 30
        if not (0 <= number <= max_score):
            return [f"TOEFL score must be between 0 and {max_score}"]
    elif cert_type == "Cambridge":
        if not (80 <= number <= 230):
            return ["Cambridge score usually sits between 80 and 230"]
    return []


def validate_fields(cert_type: str, fields: list[dict]) -> tuple[list[dict], dict]:
    valid_count = 0
    missing_required = 0
    low_confidence = 0
    values_by_key = {field.get("key", ""): str(field.get("value") or "").strip() for field in fields}

    for field in fields:
        warnings = list(field.get("warnings") or [])
        value = str(field.get("value") or "").strip()
        key = field.get("key", "")
        confidence = float(field.get("confidence") or 0.0)

        if field.get("required") and not value:
            warnings.append("required field is missing")
            missing_required += 1

        if value and confidence < 0.55:
            warnings.append("low extraction confidence")
            low_confidence += 1

        if value and (key.endswith("_date") or key.endswith(".test_date") or key.endswith(".birth_date")) and not _looks_like_date(value):
            warnings.append("date format needs review")

        if value and key.startswith("score."):
            warnings.extend(_validate_score(cert_type, key, value))

        if value and key.endswith(".id") and len(re.sub(r"\W+", "", value)) < 5:
            warnings.append("identifier looks too short")

        if value and cert_type == "TOEIC" and key.endswith(".id") and _looks_like_date(value):
            warnings.append("identifier was confused with a date")

        if value and cert_type == "TOEIC" and key == "score.total":
            listening = _parse_float(values_by_key.get("score.listening", ""))
            reading = _parse_float(values_by_key.get("score.reading", ""))
            total_score = _parse_float(value)
            if listening is not None and reading is not None and total_score is not None:
                if abs((listening + reading) - total_score) > 0.001:
                    warnings.append("TOEIC total should equal listening plus reading")

        field["warnings"] = list(dict.fromkeys(warnings))
        if not value:
            field["status"] = "missing"
        elif field["warnings"]:
            field["status"] = "review"
        else:
            field["status"] = "valid"
            valid_count += 1

    total = len(fields)
    review_count = sum(1 for field in fields if field["status"] == "review")
    return fields, {
        "total_fields": total,
        "valid_fields": valid_count,
        "review_fields": review_count,
        "missing_required": missing_required,
        "low_confidence": low_confidence,
        "completion_rate": round(valid_count / total, 4) if total else 0,
    }
