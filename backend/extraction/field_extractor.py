import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from ocr.base import OCRPage, OCRWord

from .schema import FieldSpec, get_schema

IELTS_TRF_COUNTRY_CODES = {
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AR", "AS", "AT", "AU", "AW", "AX", "AZ",
    "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ", "BR",
    "BS", "BT", "BU", "BV", "BW", "BY", "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK",
    "CL", "CM", "CN", "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR",
    "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS",
    "GT", "GU", "GW", "GY", "HK", "HM", "HN", "HR", "HT", "HU", "IA", "ID", "IE", "IL", "IM", "IN",
    "IO", "IQ", "IR", "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN",
    "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV",
    "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MQ",
    "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI",
    "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM",
    "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW", "SA", "SB", "SC",
    "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV",
    "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR",
    "TT", "TV", "TW", "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW",
}


@dataclass
class TextLine:
    text: str
    bbox: list[int]
    confidence: float
    words: list[OCRWord]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9. ]+", " ", (text or "").lower()).strip()


def _bbox_union(boxes: list[list[int]]) -> list[int]:
    if not boxes:
        return [0, 0, 0, 0]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def build_lines(page: OCRPage) -> list[TextLine]:
    if not page.words:
        return []

    words = sorted(page.words, key=lambda w: ((w.bbox[1] + w.bbox[3]) / 2, w.bbox[0]))
    lines: list[list[OCRWord]] = []

    for word in words:
        cy = (word.bbox[1] + word.bbox[3]) / 2
        placed = False
        for line in lines:
            ly = sum((w.bbox[1] + w.bbox[3]) / 2 for w in line) / len(line)
            avg_h = sum(max(1, w.bbox[3] - w.bbox[1]) for w in line) / len(line)
            if abs(cy - ly) <= max(12, avg_h * 0.7):
                line.append(word)
                placed = True
                break
        if not placed:
            lines.append([word])

    out: list[TextLine] = []
    for line_words in lines:
        line_words.sort(key=lambda w: w.bbox[0])
        text = " ".join(w.text for w in line_words)
        bbox = _bbox_union([w.bbox for w in line_words])
        confidence = sum(w.confidence for w in line_words) / len(line_words)
        out.append(TextLine(text=text, bbox=bbox, confidence=confidence, words=line_words))
    return out


def _clean_candidate_value(value: str, spec: FieldSpec) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" :;-|")
    if spec.value_hint.endswith("score"):
        value = value.replace("O", "0").replace("o", "0")
    if spec.value_hint in {"id", "toeic_score", "toeic_total", "toefl_score", "toefl_total", "cambridge_score"}:
        value = re.sub(r"[^A-Za-z0-9./ -]", "", value).strip()
    return value[:120]


def _clean_name(value: str) -> str:
    value = re.sub(r"[^A-Za-zÀ-ỹ .'-]", " ", value or "")
    value = re.sub(
        r"\b(Name|Family|First|Finst|Famly|Candidate|Candidater|Number|Centre|Date|Details|Sex|Scheme|Code)\b",
        " ",
        value,
        flags=re.I,
    )
    value = re.sub(r"\s+", " ", value).strip()
    return value.upper()


def _clean_toeic_name(value: str) -> str:
    value = re.sub(r"^\s*\d+\s*[-.)]?\s*", " ", value or "")
    value = re.sub(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", " ", value)
    value = re.sub(r"\b\d{5,}\b", " ", value)
    value = re.sub(
        r"\b(TOEIC|ETS|LISTENING|READING|TOTAL|SCORE|SCORES|YOUR|OFFICIAL|INSTITUTIONAL|PROGRAM|REPORT|CERTIFICATE|CERTIFIFICATE|NAME|TEST|VALID|UNTIL|DATE|IDENTIFICATION|NUMBER|BIRTH|KNOW|ENGLISH|SUCCESS)\b",
        " ",
        value,
        flags=re.I,
    )
    value = _clean_name(value)
    parts = [part for part in value.split() if len(part) > 1]
    return " ".join(parts)


def _clean_toefl_name(value: str) -> str:
    value = re.sub(r"^\s*Name\s*:+\s*", " ", value or "", flags=re.I)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[,;:|/\\-]+", " ", value)
    value = re.sub(
        r"\b(THIS\w*|BAPO\w*|APDF|PDF|DOWNLOADED\w*|DOWNLDADED\w*|PRINTED\w*|PINTED\w*|MINTED|BYTHE\w*|AYTHE\w*|"
        r"TEST|TAKER|TARER|TAKEKS|INTENDED\w*|PERSONAL\w*|RECORDS?|SCORE|REPORT|POF|BTT|THE|AND|FOR|FROM|"
        r"LAST|FAMILY|FAMIY|FAMLY|SUMAME|SUMANE|SURNAME|FIRST|FNT|FRST|GIVEN|GHEN|GHRE|MIDDLE|MIDDIE|MODE|"
        r"NAME|NEME|NAR|LOUFAMLYSIUMAME|LAUTE|SY|BY|RE|NI|LNDU|DOR|IEST|IESI|IHE|PEISONAL|TESTTAKERSI|TESYTAKERSI|"
        r"RICORDS|TESTTAKER|THSSAPDE|IHSSAPOFE|TAKEE|SPERSONAL|LASTLFAMIY|FAMILYLERNAMEY|FAMAYSUMANE|FAMDYSUNAME|"
        r"LALVENY|GHENT|PIST|FRT|FRAT|GIVENI|MIDDE|C'?AMIYSAMAME)\b",
        " ",
        value,
        flags=re.I,
    )
    value = re.sub(r"[^A-Za-zÀ-ỹ .'-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    parts = [part for part in value.split() if len(part) > 1]
    return " ".join(parts).upper()


def _normalize_ielts_score(value: str) -> str:
    raw = (value or "").upper().replace("O", "0").replace(",", ".")
    raw = re.sub(r"[^0-9.]", "", raw)
    if not raw:
        return ""
    try:
        number = float(raw)
    except ValueError:
        return ""

    if number > 9:
        if number <= 90 and number % 5 == 0:
            number = number / 10
        elif number <= 99:
            number = round(number / 10, 1)

    if not 0 <= number <= 9:
        return ""

    number = round(number * 2) / 2
    if abs(number - int(number)) < 0.001:
        return f"{number:.1f}"
    return f"{number:.1f}"


def _normalize_ielts_date(value: str) -> str:
    value = re.sub(r"\s+", "", value or "").upper()
    value = value.replace("00T", "OCT").replace("0CT", "OCT").replace("SEPT", "SEP")
    match = re.search(r"(\d{1,2})/?([A-Z]{3})/?(\d{4})", value)
    if not match:
        return value
    return f"{int(match.group(1)):02d}/{match.group(2)}/{match.group(3)}"


def _valid_ielts_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{2}/(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)/\d{4}", value or ""))


def _valid_ielts_trf(value: str) -> bool:
    candidate = _normalize_ielts_trf(value)
    if not re.fullmatch(r"\d{2}[A-Z]{2}\d{5,6}[A-Z]{2,5}\d{3,4}[A-Z]", candidate or ""):
        return False
    if not re.search(r"[A-Z]", candidate) or not re.search(r"\d", candidate):
        return False
    if candidate in {"ORGANISATIONS", "UNDERGRADUATE", "POSTGRADUATE", "CANDIDATE", "VALIDATION"}:
        return False
    return True


def _fix_ocr_digits(value: str) -> str:
    table = str.maketrans(
        {
            "O": "0",
            "Q": "0",
            "D": "0",
            "I": "1",
            "L": "1",
            "T": "1",
            "Z": "2",
            "S": "5",
            "B": "8",
            "G": "6",
        }
    )
    return value.translate(table)


def _fix_ocr_letters(value: str) -> str:
    table = str.maketrans(
        {
            "0": "O",
            "1": "I",
            "2": "Z",
            "5": "S",
            "6": "G",
            "8": "B",
        }
    )
    return value.translate(table)


def _alnum_windows(value: str, min_len: int = 15, max_len: int = 22) -> list[str]:
    windows = []
    for start in range(len(value)):
        for length in range(max_len, min_len - 1, -1):
            end = start + length
            if end <= len(value):
                windows.append(value[start:end])
    return windows


def _normalize_ielts_trf(value: str) -> str:
    raw = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    if not raw:
        return ""

    ignored = {
        "TEST",
        "REPORT",
        "FORM",
        "NUMBER",
        "ORGANISATIONS",
        "UNDERGRADUATE",
        "POSTGRADUATE",
        "CANDIDATE",
        "VALIDATION",
    }
    if raw in ignored:
        return ""

    candidates = [raw]
    candidates.extend(_alnum_windows(raw))

    best_value = ""
    best_score = -1
    for candidate in candidates:
        if not 15 <= len(candidate) <= 22:
            continue
        for number_len in (6, 5):
            for name_len in (4, 3, 2, 5):
                for centre_len in (3, 4):
                    if 2 + 2 + number_len + name_len + centre_len + 1 != len(candidate):
                        continue
                    year = _fix_ocr_digits(candidate[:2])
                    country = _fix_ocr_letters(candidate[2:4])
                    number = _fix_ocr_digits(candidate[4 : 4 + number_len])
                    name_start = 4 + number_len
                    name = _fix_ocr_letters(candidate[name_start : name_start + name_len])
                    centre_start = name_start + name_len
                    centre = _fix_ocr_digits(candidate[centre_start : centre_start + centre_len])
                    suffix = _fix_ocr_letters(candidate[-1])
                    fixed = f"{year}{country}{number}{name}{centre}{suffix}"

                    if not re.fullmatch(r"\d{2}[A-Z]{2}\d{5,6}[A-Z]{2,5}\d{3,4}[A-Z]", fixed):
                        continue
                    year_i = int(year)
                    if not 10 <= year_i <= 35:
                        continue
                    if country not in IELTS_TRF_COUNTRY_CODES:
                        continue

                    score = 0
                    score += 8 if number_len == 6 else 5
                    score += 5 if name_len == 4 else 3
                    score += 3 if centre_len == 3 else 1
                    score += sum(1 for a, b in zip(candidate, fixed) if a == b)
                    if score > best_score:
                        best_score = score
                        best_value = fixed

    return best_value or raw


def _ielts_trf_candidates_from_text(text: str) -> list[str]:
    upper = (text or "").upper()
    segments = []
    for label in re.finditer(
        r"(?:TEST\s+)?(?:NUMBER\s+)?REPORT\s+FORM(?:\s+NUMBER)?|TEST\s+REPORT\s+FORM|FORM\s+NUMBER|NUNBER|NUMBER",
        upper,
        flags=re.I,
    ):
        segments.append(upper[label.end() : label.end() + 90])
    if upper not in segments:
        segments.append(upper)

    candidates = []
    for segment in segments:
        cleaned = re.sub(r"TEST|REPORT|FORM|NUMBER|NUNBER|NUM8ER|TRF|CERTIFICATE", " ", segment, flags=re.I)
        compact = re.sub(r"[^A-Z0-9]", "", cleaned)
        for window in _alnum_windows(compact):
            normalized = _normalize_ielts_trf(window)
            if _valid_ielts_trf(normalized):
                candidates.append(normalized)
    return list(dict.fromkeys(candidates))


def _repair_ielts_trf_with_candidate_number(trf: str, candidate_number: str) -> str:
    trf = _normalize_ielts_trf(trf)
    candidate_number = _fix_ocr_digits(re.sub(r"[^A-Z0-9]", "", (candidate_number or "").upper()))
    if not trf or not re.fullmatch(r"\d{5,6}", candidate_number or ""):
        return trf

    match = re.fullmatch(r"(\d{2}[A-Z]{2})(\d{5,6})([A-Z]{2,5}\d{3,4}[A-Z])", trf)
    if not match:
        return trf

    current_number = match.group(2)
    candidate_variants = [candidate_number]
    if len(candidate_number) == 6 and candidate_number.endswith("0"):
        candidate_variants.append(candidate_number[:5])

    for candidate_variant in candidate_variants:
        if current_number == candidate_variant:
            return trf
        if len(current_number) == len(candidate_variant) + 1 and current_number.startswith(candidate_variant):
            shifted_letter = _fix_ocr_letters(current_number[-1])
            fixed = f"{match.group(1)}{candidate_variant}{shifted_letter}{match.group(3)}"
            if _valid_ielts_trf(fixed):
                return fixed
        if current_number in candidate_variant or candidate_variant in current_number:
            fixed = f"{match.group(1)}{candidate_variant}{match.group(3)}"
            if _valid_ielts_trf(fixed):
                return fixed
    return trf


def _cefr_from_ielts_score(value: str) -> str:
    score = _normalize_ielts_score(value)
    if not score:
        return ""
    number = float(score)
    if number >= 8.5:
        return "C2"
    if number >= 7.0:
        return "C1"
    if number >= 5.5:
        return "B2"
    if number >= 4.0:
        return "B1"
    return ""


def _extract_pattern(text: str, spec: FieldSpec) -> str:
    for pattern in spec.patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _clean_candidate_value(match.group(0), spec)
    return ""


def _alias_score(alias: str, line_text: str) -> float:
    alias_n = _norm(alias)
    line_n = _norm(line_text)
    if not alias_n or not line_n:
        return 0.0
    if alias_n in line_n:
        return 1.0
    return SequenceMatcher(None, alias_n, line_n).ratio()


def _nearby_lines(lines: list[TextLine], anchor_idx: int, page: OCRPage) -> list[TextLine]:
    anchor = lines[anchor_idx]
    ax1, ay1, ax2, ay2 = anchor.bbox
    candidates: list[tuple[float, TextLine]] = []
    for i, line in enumerate(lines):
        if i == anchor_idx:
            continue
        x1, y1, x2, y2 = line.bbox
        same_row = abs(((y1 + y2) / 2) - ((ay1 + ay2) / 2)) < max(18, (ay2 - ay1) * 1.4)
        below = y1 >= ay1 and y1 - ay2 < page.height * 0.08
        right = x1 >= ax1 and x1 - ax2 < page.width * 0.35
        if same_row or below or right:
            dist = abs(y1 - ay1) + max(0, x1 - ax2) * 0.4
            candidates.append((dist, line))
    return [line for _, line in sorted(candidates, key=lambda item: item[0])[:5]]


def _extract_from_anchor(spec: FieldSpec, lines: list[TextLine], page: OCRPage) -> dict[str, Any] | None:
    best_anchor: tuple[float, int] | None = None
    for idx, line in enumerate(lines):
        score = max((_alias_score(alias, line.text) for alias in spec.aliases), default=0.0)
        if score >= 0.72 and (best_anchor is None or score > best_anchor[0]):
            best_anchor = (score, idx)

    if best_anchor is None:
        return None

    score, idx = best_anchor
    anchor = lines[idx]
    search_texts = [anchor.text] + [line.text for line in _nearby_lines(lines, idx, page)]
    joined = " ".join(search_texts)
    value = _extract_pattern(joined, spec)

    if not value:
        line_norm = anchor.text
        for alias in spec.aliases:
            line_norm = re.sub(re.escape(alias), "", line_norm, flags=re.I)
        value = _clean_candidate_value(line_norm, spec)

    if not value:
        return None

    return {
        "value": value,
        "confidence": min(0.98, 0.45 + score * 0.35 + anchor.confidence * 0.2),
        "bbox": anchor.bbox,
        "evidence": joined[:300],
        "source": "anchor",
    }


def _extract_global_pattern(spec: FieldSpec, full_text: str, page: OCRPage) -> dict[str, Any] | None:
    value = _extract_pattern(full_text, spec)
    if not value:
        return None

    match_words = [w for w in page.words if value.lower() in w.text.lower() or w.text.lower() in value.lower()]
    bbox = _bbox_union([w.bbox for w in match_words[:4]]) if match_words else [0, 0, 0, 0]
    return {
        "value": value,
        "confidence": 0.55,
        "bbox": bbox,
        "evidence": value,
        "source": "pattern",
    }


def _field_has_value(fields_by_key: dict[str, dict[str, Any]], key: str) -> bool:
    return bool(str(fields_by_key.get(key, {}).get("value") or "").strip())


def _field_has_valid_ielts_date(fields_by_key: dict[str, dict[str, Any]], key: str) -> bool:
    return _valid_ielts_date(_normalize_ielts_date(str(fields_by_key.get(key, {}).get("value") or "")))


def _set_field(fields_by_key: dict[str, dict[str, Any]], key: str, value: str, line: TextLine, source: str) -> None:
    if key not in fields_by_key or not value:
        return
    if key.startswith("score.") and source.startswith("ielts"):
        normalized_score = _normalize_ielts_score(value)
        if not normalized_score:
            return
        value = normalized_score
    elif key == "candidate.full_name":
        if source.startswith("toeic"):
            value = _clean_toeic_name(value)
        elif source.startswith("toefl"):
            value = _clean_toefl_name(value)
        else:
            value = _clean_name(value)
    elif key == "candidate.test_date" and source.startswith("ielts"):
        value = _normalize_ielts_date(value)
        if not _valid_ielts_date(value):
            return
    elif key == "candidate.id" and source.startswith("toeic"):
        if re.fullmatch(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", value.strip()):
            return
    elif key == "certificate.number":
        if source.startswith("ielts"):
            value = _normalize_ielts_trf(value)
            if not _valid_ielts_trf(value):
                return
        else:
            value = re.sub(r"[^A-Z0-9]", "", value.upper())
    fields_by_key[key].update(
        {
            "value": _clean_candidate_value(value, FieldSpec(key=key, label=key)),
            "confidence": max(float(fields_by_key[key].get("confidence") or 0.0), float(line.confidence or 0.0)),
            "bbox": line.bbox,
            "evidence": line.text,
            "source": source,
        }
    )


def _ielts_centre_stamp_context(lines: list[TextLine]) -> tuple[str, TextLine | None]:
    start_idx = next(
        (
            idx
            for idx, line in enumerate(lines)
            if re.search(r"C(?:E|A)NTR[EA]?\s+ST[AE]MP|CENTER\s+STAMP|CENTRE\s+STAMP", line.text, flags=re.I)
        ),
        -1,
    )
    if start_idx < 0:
        return "", None

    context_lines: list[TextLine] = []
    for line in lines[start_idx : min(len(lines), start_idx + 7)]:
        if context_lines and re.search(r"Test\s+Report|Form\s+Number|\bDate\b|Administrator", line.text, flags=re.I):
            break
        context_lines.append(line)
    return " ".join(line.text for line in context_lines), context_lines[0] if context_lines else lines[start_idx]


def _ielts_organizer_from_stamp(lines: list[TextLine]) -> tuple[str, TextLine | None, str]:
    stamp_context, stamp_line = _ielts_centre_stamp_context(lines)
    if re.search(r"\bIDP\b|IELTS\s+TEST\s+CENT(?:RE|ER)S?", stamp_context, flags=re.I):
        return "IDP", stamp_line, stamp_context
    if re.search(r"BRIT|COUNCIL", stamp_context, flags=re.I):
        return "British Council", stamp_line, stamp_context
    return "IDP", stamp_line, stamp_context or "defaulted: no British/Council evidence near Centre stamp"


def _apply_ielts_layout_overrides(fields: list[dict[str, Any]], lines: list[TextLine]) -> None:
    fields_by_key = {field["key"]: field for field in fields}
    all_text = "\n".join(line.text for line in lines)
    family_name = ""
    first_name = ""
    candidate_number = ""

    for line in lines:
        text = line.text

        if not candidate_number:
            candidate_number_match = re.search(r"Candid(?:ate|ater)?\s+Number\s+([A-Z0-9]{5,8})", text, flags=re.I)
            if candidate_number_match:
                candidate_number = _fix_ocr_digits(candidate_number_match.group(1))

        if "Centre Number" in text and "Candidate Number" in text:
            match = re.search(r"\bDate\s+(\d{1,2}/?[A-Z0-9]{3}/?\d{4})\b", text, flags=re.I)
            if match:
                _set_field(fields_by_key, "candidate.test_date", match.group(1), line, "ielts_layout")
            candidate_number_match = re.search(r"Candidate\s+Number\s+([A-Z0-9]{5,8})", text, flags=re.I)
            if candidate_number_match:
                candidate_number = _fix_ocr_digits(candidate_number_match.group(1))

        if re.search(r"Candid(?:ate|ale)\s+ID", text, flags=re.I):
            match = re.search(r"Candid(?:ate|ale)\s+ID\s+([A-Z0-9]{6,})", text, flags=re.I)
            if match:
                _set_field(fields_by_key, "candidate.id", match.group(1), line, "ielts_layout")

        family_match = re.search(r"Fam(?:i|l)?ly\s+Name\s+(.+)$|Famly\s+Name\s+(.+)$", text, flags=re.I)
        if family_match:
            family_name = _clean_name(family_match.group(1) or family_match.group(2) or "")

        first_match = re.search(r"F(?:i|1)?r?s?t\s+Name(?:\(s\))?\s+(.+)$|Finst\s+Name\s+(.+)$", text, flags=re.I)
        if first_match:
            first_name = _clean_name(first_match.group(1) or first_match.group(2) or "")

        if family_name or first_name:
            full_name = " ".join(part for part in [family_name, first_name] if part)
            if full_name:
                _set_field(fields_by_key, "candidate.full_name", full_name, line, "ielts_layout")

        if "Listening" in text and "Reading" in text and "Writing" in text and "Speaking" in text:
            token = r"(\d{2}|\d(?:\.\d)?)"
            score_patterns = {
                "score.listening": rf"Listening\s+{token}",
                "score.reading": rf"Reading\s+{token}",
                "score.writing": rf"Writing\s+{token}",
                "score.speaking": rf"Speaking\s+{token}",
                "score.overall": rf"(?:Overall\s+Band(?:\s+Score)?|Band\s+Overall|Band(?:\s+Score)?)\s+{token}",
            }
            for key, pattern in score_patterns.items():
                match = re.search(pattern, text, flags=re.I)
                if match:
                    _set_field(fields_by_key, key, match.group(1), line, "ielts_layout")
            cefr_match = re.search(r"(?:CEFR\s+Level|CEFR|Level)\s+([ABC][12])", text, flags=re.I)
            if cefr_match:
                _set_field(fields_by_key, "cefr.level", cefr_match.group(1).upper(), line, "ielts_layout")

    if not _field_has_valid_ielts_date(fields_by_key, "candidate.test_date"):
        for line in lines:
            if line.bbox[1] > 0 and line.bbox[1] > max(650, (max((candidate.bbox[3] for candidate in lines), default=0) * 0.55)):
                continue
            if not re.search(r"Date|Centre|Center|Candidate|IELTS|Report|Details", line.text, flags=re.I):
                continue
            match = re.search(r"(\d{1,2}\s*/?\s*[A-Z0-9]{3}\s*/?\s*\d{4})", line.text, flags=re.I)
            if match:
                _set_field(fields_by_key, "candidate.test_date", match.group(1), line, "ielts_layout_regex")
                if _field_has_valid_ielts_date(fields_by_key, "candidate.test_date"):
                    break

    trf_candidates: list[tuple[int, TextLine, str]] = []
    for idx, line in enumerate(lines):
        text = line.text.upper()
        window = " ".join(candidate.text for candidate in lines[max(0, idx - 1) : min(len(lines), idx + 3)])
        if re.search(r"TEST|REPORT|FORM|NUNBER|NUMBER", text, flags=re.I):
            for candidate in _ielts_trf_candidates_from_text(window):
                score = 0
                if re.search(r"REPORT|FORM", window, flags=re.I):
                    score += 4
                if re.search(r"NUMBER|NUNBER", window, flags=re.I):
                    score += 2
                if 0.45 <= (line.bbox[1] / max(1, max((candidate_line.bbox[3] for candidate_line in lines), default=1))) <= 0.95:
                    score += 2
                score += len(candidate)
                trf_candidates.append((score, line, candidate))
    if trf_candidates:
        _, line, candidate = sorted(trf_candidates, key=lambda item: item[0], reverse=True)[0]
        _set_field(fields_by_key, "certificate.number", candidate, line, "ielts_layout")

    issuer, issuer_line, issuer_evidence = _ielts_organizer_from_stamp(lines)
    if issuer_line:
        fields_by_key["issuer"].update(
            {
                "value": issuer,
                "confidence": max(float(fields_by_key["issuer"].get("confidence") or 0.0), 0.91 if issuer == "IDP" else 0.88),
                "bbox": issuer_line.bbox,
                "evidence": issuer_evidence[:300],
                "source": "ielts_centre_stamp",
            }
        )
    elif lines and "issuer" in fields_by_key:
        fields_by_key["issuer"].update(
            {
                "value": issuer,
                "confidence": 0.72,
                "bbox": lines[-1].bbox,
                "evidence": issuer_evidence,
                "source": "ielts_organizer_rule",
            }
        )

    for key in ["score.listening", "score.reading", "score.writing", "score.speaking", "score.overall"]:
        field = fields_by_key.get(key)
        if not field:
            continue
        normalized = _normalize_ielts_score(str(field.get("value") or ""))
        field["value"] = normalized
        if not normalized:
            field["confidence"] = 0.0
            field["source"] = "missing"
            field["evidence"] = ""
            field["bbox"] = [0, 0, 0, 0]

    cefr_field = fields_by_key.get("cefr.level")
    if cefr_field and not re.fullmatch(r"[ABC][12]", str(cefr_field.get("value") or "").strip(), flags=re.I):
        derived = _cefr_from_ielts_score(str(fields_by_key.get("score.overall", {}).get("value") or ""))
        cefr_field["value"] = derived
        cefr_field["confidence"] = 0.75 if derived else 0.0
        cefr_field["source"] = "ielts_score_mapping" if derived else "missing"
        cefr_field["evidence"] = "derived from overall band score" if derived else ""

    date_field = fields_by_key.get("candidate.test_date")
    if date_field:
        normalized = _normalize_ielts_date(str(date_field.get("value") or ""))
        if _valid_ielts_date(normalized):
            date_field["value"] = normalized
        else:
            date_field.update({"value": "", "confidence": 0.0, "bbox": [0, 0, 0, 0], "evidence": "", "source": "missing"})

    trf_field = fields_by_key.get("certificate.number")
    if trf_field:
        candidate = _repair_ielts_trf_with_candidate_number(str(trf_field.get("value") or ""), candidate_number)
        if _valid_ielts_trf(candidate):
            trf_field["value"] = candidate
        else:
            trf_field.update({"value": "", "confidence": 0.0, "bbox": [0, 0, 0, 0], "evidence": "", "source": "missing"})


def _toeic_dates(text: str) -> list[str]:
    return re.findall(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", text or "")


def _toeic_numbers(text: str, max_value: int = 990) -> list[int]:
    text = re.sub(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", " ", text or "")
    numbers = []
    for raw in re.findall(r"\b\d{2,3}\b", text):
        number = int(raw)
        if 5 <= number <= max_value:
            numbers.append(number)
    return numbers


def _toeic_score_from_line(text: str) -> int | None:
    match = re.search(r"Your\s+score\s*\(?\s*(\d{2,3})", text or "", flags=re.I)
    if match:
        number = int(match.group(1))
        if 5 <= number <= 495:
            return number
    numbers = [n for n in _toeic_numbers(text, 495) if n <= 495]
    if not numbers:
        return None
    return numbers[-1]


def _toeic_context(lines: list[TextLine], idx: int, radius: int = 2) -> str:
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius + 1)
    return " ".join(line.text for line in lines[start:end])


def _set_toeic_score(fields_by_key: dict[str, dict[str, Any]], key: str, value: int | None, line: TextLine) -> None:
    if value is None:
        return
    if key.endswith("total"):
        if not 10 <= value <= 990:
            return
    elif not 5 <= value <= 495:
        return
    _set_field(fields_by_key, key, str(value), line, "toeic_layout")


def _apply_toeic_layout_overrides(fields: list[dict[str, Any]], lines: list[TextLine]) -> None:
    fields_by_key = {field["key"]: field for field in fields}
    for idx, line in enumerate(lines):
        text = line.text
        upper = text.upper()

        if "THIS IS TO CERTIFY THAT" in upper and idx + 1 < len(lines):
            name = _clean_toeic_name(lines[idx + 1].text)
            if name:
                _set_field(fields_by_key, "candidate.full_name", name, lines[idx + 1], "toeic_layout")

        if "LISTENING" in upper and not re.search(r"\b(SCALE|TOCICS|BUSINESS|DEVELOPMENT)\b", upper):
            name = _clean_toeic_name(re.split(r"\bLISTENING\b", text, flags=re.I)[0])
            if len(name.split()) >= 2:
                _set_field(fields_by_key, "candidate.full_name", name, line, "toeic_layout")

        if "SCORE" in upper and "YOUR SCORE" not in upper and not re.search(r"\b(OFFICIAL|TOTAL|LISTENING|READING|IDENTIFICATION)\b", upper):
            name = _clean_toeic_name(re.split(r"\bSCORE\b", text, flags=re.I)[0])
            next_text = lines[idx + 1].text if idx + 1 < len(lines) else ""
            if len(name.split()) >= 2 and re.search(r"\bName\b", next_text, flags=re.I):
                _set_field(fields_by_key, "candidate.full_name", name, line, "toeic_layout")

        context = _toeic_context(lines, idx, 4).upper()
        local_previous = " ".join(l.text.upper() for l in lines[max(0, idx - 1) : idx + 1])
        if "YOUR SCORE" in upper or re.search(r"\bNAME\b", upper):
            score = _toeic_score_from_line(text)
            if score is not None and "LISTENING" in context and "READING" not in local_previous:
                _set_toeic_score(fields_by_key, "score.listening", score, line)
        if ("YOUR SCORE" in upper or _toeic_dates(text)) and "READING" in context:
            score = _toeic_score_from_line(text)
            if score is not None:
                _set_toeic_score(fields_by_key, "score.reading", score, line)

        if re.fullmatch(r"\s*\d{2,3}\s*", text or "") and idx > 0:
            number = int(text.strip())
            if 10 <= number <= 990 and "TOTAL" in _toeic_context(lines, idx, 3).upper():
                _set_toeic_score(fields_by_key, "score.total", number, line)

        cert_match = re.search(r"\bListening\s+(\d{2,3})\b", text, flags=re.I)
        if cert_match:
            _set_toeic_score(fields_by_key, "score.listening", int(cert_match.group(1)), line)
        cert_match = re.search(r"\bReading\s+(\d{2,3})\b", text, flags=re.I)
        if cert_match:
            _set_toeic_score(fields_by_key, "score.reading", int(cert_match.group(1)), line)
        cert_match = re.search(r"\bTotal\s+(\d{2,3})\b", text, flags=re.I)
        if cert_match:
            _set_toeic_score(fields_by_key, "score.total", int(cert_match.group(1)), line)

        if re.search(r"\bdate:\s*", text, flags=re.I):
            value = re.sub(r".*\bdate:\s*", "", text, flags=re.I).strip()
            _set_field(fields_by_key, "candidate.test_date", value, line, "toeic_layout")

        if "IDENTIFICATION" in upper and idx > 0:
            candidate_lines = lines[max(0, idx - 3) : min(len(lines), idx + 2)]
            joined = " ".join(candidate.text for candidate in candidate_lines)
            dates = _toeic_dates(joined)
            no_dates = re.sub(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", " ", joined)
            ids = [m for m in re.findall(r"\b\d{6,20}\b", no_dates) if not re.fullmatch(r"\d{2,3}", m)]
            if ids:
                id_line = next((candidate for candidate in candidate_lines if ids[0] in candidate.text), line)
                _set_field(fields_by_key, "candidate.id", ids[0][:12], id_line, "toeic_layout")
            if dates:
                date_line = next((candidate for candidate in candidate_lines if dates[0] in candidate.text), line)
                _set_field(fields_by_key, "candidate.birth_date", dates[0], date_line, "toeic_layout")

        if "Test Date" in text or ("Valid" in text and "Until" in text):
            candidate_lines = lines[max(0, idx - 3) : min(len(lines), idx + 2)]
            joined = " ".join(candidate.text for candidate in candidate_lines)
            dates = _toeic_dates(joined)
            if len(dates) >= 2:
                date_line = next((candidate for candidate in candidate_lines if dates[-2] in candidate.text), line)
                _set_field(fields_by_key, "candidate.test_date", dates[-2], date_line, "toeic_layout")

        if "Name" in text and "Client/Institution" not in text and idx > 0:
            prev = lines[idx - 1]
            if re.search(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}|yyyy|Test|Valid", prev.text, flags=re.I):
                continue
            name = _clean_toeic_name(re.sub(r"\b\d{2,3}\)?\b", "", prev.text).strip(" )("))
            if name:
                _set_field(fields_by_key, "candidate.full_name", name, prev, "toeic_layout")
            score = re.search(r"\b([1-4]\d{2}|[5-9]\d)\)?\b", prev.text)
            if score and not str(fields_by_key.get("score.listening", {}).get("value") or "").strip():
                _set_field(fields_by_key, "score.listening", score.group(1), prev, "toeic_layout")

        if "Identification Number" in text and idx > 0:
            prev = lines[idx - 1]
            matches = re.findall(r"\b\d{4}/\d{2}/\d{2}\b|\b\d{6,12}\b", prev.text)
            if matches:
                _set_field(fields_by_key, "candidate.id", matches[0], prev, "toeic_layout")
            if len(matches) >= 2:
                _set_field(fields_by_key, "candidate.birth_date", matches[1], prev, "toeic_layout")

        if "Date Valid" in text and idx > 0:
            prev = next(
                (candidate for candidate in reversed(lines[max(0, idx - 3) : idx]) if re.search(r"\d{4}/\d{2}/\d{2}", candidate.text)),
                lines[idx - 1],
            )
            dates = re.findall(r"\b\d{4}/\d{2}/\d{2}\b", prev.text)
            score_text = re.sub(r"\b\d{4}/\d{2}/\d{2}\b", " ", prev.text)
            nums = [int(n) for n in re.findall(r"\b\d{2,3}\b", score_text)]
            if dates:
                _set_field(fields_by_key, "candidate.test_date", dates[0], prev, "toeic_layout")
            if len(nums) >= 2:
                reading = next((n for n in nums if 5 <= n <= 495), None)
                total = next((n for n in nums if 10 <= n <= 990 and n > 495), None)
                if reading:
                    _set_field(fields_by_key, "score.reading", str(reading), prev, "toeic_layout")
                if total:
                    _set_field(fields_by_key, "score.total", str(total), prev, "toeic_layout")

    listening = fields_by_key.get("score.listening", {}).get("value")
    reading = fields_by_key.get("score.reading", {}).get("value")
    try:
        listening_i = int(float(str(listening)))
        reading_i = int(float(str(reading)))
    except Exception:
        listening_i = reading_i = 0
    total = listening_i + reading_i
    if 10 <= total <= 990 and listening_i and reading_i:
        anchor = next(
            (line for line in lines if str(reading_i) in line.text or str(listening_i) in line.text),
            lines[-1] if lines else TextLine("", [0, 0, 0, 0], 0.75, []),
        )
        fields_by_key["score.total"].update(
            {
                "value": str(total),
                "confidence": max(float(fields_by_key["score.total"].get("confidence") or 0.0), 0.92),
                "bbox": anchor.bbox,
                "evidence": "listening + reading consistency check",
                "source": "toeic_score_sum",
            }
        )


def _apply_toefl_layout_overrides(fields: list[dict[str, Any]], lines: list[TextLine]) -> None:
    fields_by_key = {field["key"]: field for field in fields}
    for idx, line in enumerate(lines):
        text = line.text
        if re.search(r"^\s*Name\s*:+", text, flags=re.I):
            match = re.search(r"Name\s*:+\s*(.+)$", text, flags=re.I)
            if match:
                _set_field(fields_by_key, "candidate.full_name", match.group(1), line, "toefl_layout")

        if "Appointment Number" in text or "Registration Number" in text:
            match = re.search(r"(?:Appointment|Registration)\s+Number:\s*([0-9: ]{8,})", text, flags=re.I)
            if match:
                _set_field(fields_by_key, "candidate.id", re.sub(r"[^0-9 ]", " ", match.group(1)).strip(), line, "toefl_layout")

        if re.search(r"Test\s+Da[lt]e", text, flags=re.I):
            match = re.search(r"Test\s+Da[lt]e:\s*([0-9]{1,2}\s+[A-Za-z]{3,9}:?\s+[0-9]{4}|[A-Za-z]{3,9}\s*[0-9]{1,2},\s*[0-9]{4})", text, flags=re.I)
            if match:
                value = re.sub(r"([A-Za-z])(\d{1,2},)", r"\1 \2", match.group(1))
                value = value.replace(":", "")
                _set_field(fields_by_key, "candidate.test_date", value, line, "toefl_layout")

        if "Total Score" in text:
            total_inline = re.search(r"Total\s+Score\s*(\d{2,3})(?!\s*-)|(\d{2,3})\s+Total\s+Score\s*(\d{2,3})(?!\s*-)", text, flags=re.I)
            if total_inline:
                total_value = total_inline.group(1) or total_inline.group(3) or total_inline.group(2)
                _set_field(fields_by_key, "score.total", total_value, line, "toefl_layout")
            total_out_of = re.search(r"\b(\d{2,3})\s*/\s*120\b|\b(\d{2,3})\s+120\b", text, flags=re.I)
            if total_out_of:
                _set_field(fields_by_key, "score.total", total_out_of.group(1) or total_out_of.group(2), line, "toefl_layout")
            reading = re.search(r"Reading:?\s*(\d{1,2})(?!\s*-)", text, flags=re.I)
            if reading:
                _set_field(fields_by_key, "score.reading", reading.group(1), line, "toefl_layout")
            if idx + 1 < len(lines):
                total = re.search(r"^\s*(\d{2,3})\s+120\b", lines[idx + 1].text)
                if total:
                    _set_field(fields_by_key, "score.total", total.group(1), lines[idx + 1], "toefl_layout")

        for key, label in {
            "score.listening": "Listening",
            "score.speaking": "Speaking",
            "score.writing": "Writing",
        }.items():
            match = re.search(label + r":?\s*(\d{1,2})(?!\s*-)", text, flags=re.I)
            if match:
                _set_field(fields_by_key, key, match.group(1), line, "toefl_layout")

    section_values = []
    for key in ["score.reading", "score.listening", "score.speaking", "score.writing"]:
        try:
            section_values.append(int(str(fields_by_key.get(key, {}).get("value") or "")))
        except Exception:
            section_values.append(0)
    if all(value > 0 for value in section_values):
        total = sum(section_values)
        if total <= 120:
            anchor = next((line for line in lines if "Total Score" in line.text), lines[-1] if lines else TextLine("", [0, 0, 0, 0], 0.75, []))
            current_total = fields_by_key["score.total"].get("value")
            try:
                current_total_i = int(str(current_total))
            except Exception:
                current_total_i = 0
            if not current_total_i or current_total_i == total:
                fields_by_key["score.total"].update(
                    {
                        "value": str(total),
                        "confidence": max(float(fields_by_key["score.total"].get("confidence") or 0.0), 0.9),
                        "bbox": anchor.bbox,
                        "evidence": "TOEFL section score sum",
                        "source": "toefl_score_sum",
                    }
                )


def _apply_cambridge_layout_overrides(fields: list[dict[str, Any]], lines: list[TextLine]) -> None:
    fields_by_key = {field["key"]: field for field in fields}
    all_text = "\n".join(line.text for line in lines)
    for idx, line in enumerate(lines):
        text = line.text
        if re.search(r"This\s+\w+\s+to\s+certi", text, flags=re.I) and idx + 1 < len(lines):
            candidate = lines[idx + 1].text
            if not re.search(r"has been awarded|your name|^your$", candidate, flags=re.I):
                _set_field(fields_by_key, "candidate.full_name", candidate, lines[idx + 1], "cambridge_layout")
        if "Grade" in text:
            match = re.search(r"Grade\s+[ABC]", text, flags=re.I)
            if match:
                _set_field(fields_by_key, "grade", match.group(0), line, "cambridge_layout")
        if "Council of Europe" in text:
            match = re.search(r"\b[ABC][12]\b", text)
            if match:
                _set_field(fields_by_key, "cefr.level", match.group(0), line, "cambridge_layout")
        if "Date of Examination" in text:
            match = re.search(
                r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|AUG|SEP|OCT|NOV|DEC)\b.*?(\d{4})",
                text,
                flags=re.I,
            )
            value = f"{match.group(1).upper()} {match.group(2)}" if match else re.sub(r".*Date of Examination\s*", "", text, flags=re.I).strip(" :")
            _set_field(fields_by_key, "candidate.test_date", value, line, "cambridge_layout")
        if "Certificate Number" in text:
            match = re.search(r"\b\d{8,12}\b", text)
            if match:
                _set_field(fields_by_key, "certificate.number", match.group(0), line, "cambridge_layout")
        if "CAMBRIDGE" in text.upper() or "Cambridge" in text:
            _set_field(fields_by_key, "issuer", "University of Cambridge", line, "cambridge_layout")

    cefr_field = fields_by_key.get("cefr.level")
    if cefr_field and not re.fullmatch(r"[ABC][12]", str(cefr_field.get("value") or "").strip(), flags=re.I):
        match = re.search(r"(?:Council\s+of\s+Europe\s+)?Level\s+([ABC][12])|\b([ABC][12])\b", all_text, flags=re.I)
        cefr_field["value"] = (match.group(1) or match.group(2)).upper() if match else ""
        cefr_field["confidence"] = 0.86 if cefr_field["value"] else 0.0
        cefr_field["source"] = "cambridge_layout" if cefr_field["value"] else "missing"
        cefr_field["evidence"] = match.group(0) if match else ""

    date_field = fields_by_key.get("candidate.test_date")
    if date_field:
        match = re.search(
            r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|AUG|SEP|OCT|NOV|DEC)\b.*?(\d{4})",
            str(date_field.get("value") or ""),
            flags=re.I,
        )
        if match:
            date_field["value"] = f"{match.group(1).upper()} {match.group(2)}"

    name_field = fields_by_key.get("candidate.full_name")
    if name_field and re.search(r"^\s*(YOUR|YOUR NAME|HAS BEEN AWARDED)\s*$", str(name_field.get("value") or ""), flags=re.I):
        name_field.update({"value": "", "confidence": 0.0, "bbox": [0, 0, 0, 0], "evidence": "", "source": "missing"})


def extract_fields(cert_type: str, page: OCRPage) -> list[dict[str, Any]]:
    specs = get_schema(cert_type)
    lines = build_lines(page)
    full_text = page.plain_text()
    fields: list[dict[str, Any]] = []

    for spec in specs:
        result = _extract_from_anchor(spec, lines, page)
        if result is None:
            result = _extract_global_pattern(spec, full_text, page)

        if result is None:
            result = {
                "value": "",
                "confidence": 0.0,
                "bbox": [0, 0, 0, 0],
                "evidence": "",
                "source": "missing",
            }

        fields.append(
            {
                "key": spec.key,
                "label": spec.label,
                "value": result["value"],
                "confidence": round(float(result["confidence"]), 4),
                "bbox": result["bbox"],
                "evidence": result["evidence"],
                "source": result["source"],
                "required": spec.required,
                "status": "pending",
                "warnings": [],
            }
        )

    if cert_type == "IELTS":
        _apply_ielts_layout_overrides(fields, lines)
    elif cert_type == "TOEIC":
        _apply_toeic_layout_overrides(fields, lines)
    elif cert_type == "TOEFL":
        _apply_toefl_layout_overrides(fields, lines)
    elif cert_type == "Cambridge":
        _apply_cambridge_layout_overrides(fields, lines)

    return fields
