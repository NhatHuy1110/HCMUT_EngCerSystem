from dataclasses import dataclass, field


@dataclass
class FieldSpec:
    key: str
    label: str
    aliases: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    value_hint: str = "text"
    required: bool = True


COMMON_PATTERNS = {
    "date": [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        r"\b\d{1,2}\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[A-Z]*\s+\d{4}\b",
    ],
    "ielts_score": [r"\b[0-9](?:\.5|\.0)?\b"],
    "toeic_score": [r"\b\d{2,3}\b"],
    "toefl_score": [r"\b\d{1,3}\b"],
    "cefr": [r"\bA1\b|\bA2\b|\bB1\b|\bB2\b|\bC1\b|\bC2\b"],
}


SCHEMAS: dict[str, list[FieldSpec]] = {
    "IELTS": [
        FieldSpec("candidate.full_name", "Candidate name", ["candidate name", "family name", "first name"]),
        FieldSpec("candidate.id", "Candidate ID", ["candidate no", "candidate number", "candidate id"], [r"\b\d{5,8}\b"], "id"),
        FieldSpec("candidate.test_date", "Test date", ["test date", "date"], COMMON_PATTERNS["date"], "date"),
        FieldSpec("score.listening", "Listening", ["listening"], COMMON_PATTERNS["ielts_score"], "ielts_score"),
        FieldSpec("score.reading", "Reading", ["reading"], COMMON_PATTERNS["ielts_score"], "ielts_score"),
        FieldSpec("score.writing", "Writing", ["writing"], COMMON_PATTERNS["ielts_score"], "ielts_score"),
        FieldSpec("score.speaking", "Speaking", ["speaking"], COMMON_PATTERNS["ielts_score"], "ielts_score"),
        FieldSpec("score.overall", "Overall band", ["overall band score", "overall"], COMMON_PATTERNS["ielts_score"], "ielts_score"),
        FieldSpec("cefr.level", "CEFR level", ["cefr"], COMMON_PATTERNS["cefr"], "cefr", False),
        FieldSpec("certificate.number", "TRF number", ["test report form number", "trf number"], [r"\b[A-Z0-9]{12,22}\b"], "id"),
        FieldSpec("issuer", "Organizer", ["british council", "idp"], [r"British Council|IDP"], "issuer", False),
    ],
    "TOEIC": [
        FieldSpec("candidate.full_name", "Candidate name", ["name", "candidate name"]),
        FieldSpec("candidate.id", "Candidate ID", ["id number", "registration number"], [r"\b\d{6,12}\b"], "id"),
        FieldSpec("candidate.birth_date", "Date of birth", ["date of birth", "birth"], COMMON_PATTERNS["date"], "date", False),
        FieldSpec("candidate.test_date", "Test date", ["test date", "date"], COMMON_PATTERNS["date"], "date"),
        FieldSpec("score.listening", "Listening", ["listening"], COMMON_PATTERNS["toeic_score"], "toeic_score"),
        FieldSpec("score.reading", "Reading", ["reading"], COMMON_PATTERNS["toeic_score"], "toeic_score"),
        FieldSpec("score.total", "Total", ["total score", "total"], [r"\b\d{2,3}\b"], "toeic_total"),
        FieldSpec("issuer", "Issuer", ["ets"], [r"\bETS\b"], "issuer", False),
    ],
    "TOEFL": [
        FieldSpec("candidate.full_name", "Candidate name", ["name", "test taker"]),
        FieldSpec("candidate.id", "Registration number", ["registration number", "appointment number"], [r"\b\d{6,16}\b"], "id"),
        FieldSpec("candidate.test_date", "Test date", ["test date"], COMMON_PATTERNS["date"], "date"),
        FieldSpec("score.reading", "Reading", ["reading"], COMMON_PATTERNS["toefl_score"], "toefl_score"),
        FieldSpec("score.listening", "Listening", ["listening"], COMMON_PATTERNS["toefl_score"], "toefl_score"),
        FieldSpec("score.speaking", "Speaking", ["speaking"], COMMON_PATTERNS["toefl_score"], "toefl_score"),
        FieldSpec("score.writing", "Writing", ["writing"], COMMON_PATTERNS["toefl_score"], "toefl_score"),
        FieldSpec("score.total", "Total", ["total score", "total"], [r"\b\d{1,3}\b"], "toefl_total"),
        FieldSpec("issuer", "Issuer", ["ets"], [r"\bETS\b"], "issuer", False),
    ],
    "Cambridge": [
        FieldSpec("candidate.full_name", "Candidate name", ["name", "candidate"]),
        FieldSpec("candidate.test_date", "Issue/Test date", ["date", "session"], COMMON_PATTERNS["date"], "date"),
        FieldSpec("cefr.level", "CEFR level", ["cefr", "level"], COMMON_PATTERNS["cefr"], "cefr"),
        FieldSpec("score.overall", "Overall score", ["overall score", "score"], [r"\b1[0-9]{2,2}\b|\b2[0-3][0-9]\b"], "cambridge_score", False),
        FieldSpec("grade", "Grade", ["grade"], [r"\bGrade\s+[ABC]\b|\bPass\b|\bDistinction\b|\bMerit\b"], "text", False),
        FieldSpec("certificate.number", "Certificate number", ["certificate number"], [r"\b\d{8,12}\b"], "id", False),
        FieldSpec("issuer", "Issuer", ["cambridge"], [r"Cambridge"], "issuer", False),
    ],
}


def get_schema(cert_type: str) -> list[FieldSpec]:
    return SCHEMAS.get(cert_type, [])
