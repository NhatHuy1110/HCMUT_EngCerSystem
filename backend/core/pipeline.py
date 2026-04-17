import time
from typing import Any

from core.classifier import classify_certificate
from core.preprocessing import decode_image, preprocess_image
from extraction.field_extractor import extract_fields
from ocr.factory import get_ocr_engine
from validation.validators import validate_fields


def process_document(file_bytes: bytes, filename: str, preferred_engine: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()

    original = decode_image(file_bytes, filename)
    preprocessed = preprocess_image(original)

    engine = get_ocr_engine(preferred_engine)
    page = engine.recognize(preprocessed.image_bgr)
    text = page.plain_text()

    classification = classify_certificate(text, page.width, page.height)
    fields = extract_fields(classification.cert_type, page)
    fields, quality = validate_fields(classification.cert_type, fields)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    warnings = list(preprocessed.warnings) + list(page.warnings)
    if classification.cert_type == "Unknown":
        warnings.append("certificate type could not be determined confidently")
    if not page.words:
        warnings.append("no OCR words were detected")

    return {
        "fileName": filename,
        "certType": classification.cert_type,
        "confidence": round(classification.confidence, 4),
        "classification": classification.to_dict(),
        "fields": fields,
        "entries": {field["key"]: field["value"] for field in fields},
        "quality": quality,
        "ocr": page.to_dict(),
        "image": {
            "width": page.width,
            "height": page.height,
            "originalWidth": preprocessed.original_width,
            "originalHeight": preprocessed.original_height,
        },
        "warnings": warnings,
        "processingMs": elapsed_ms,
        "version": "document-ai-v2",
    }
