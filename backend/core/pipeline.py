import time
from typing import Any

from core.classifier import classify_certificate
from core.preprocessing import PreprocessResult, decode_image, preprocess_image
from extraction.field_extractor import extract_fields
from ocr.factory import get_ocr_engine
from validation.validators import validate_fields


def process_document(
    file_bytes: bytes,
    filename: str,
    preferred_engine: str | None = None,
    preprocessing_mode: str = "full",
) -> dict[str, Any]:
    started = time.perf_counter()
    requested_engine = (preferred_engine or "default").strip().lower()

    original = decode_image(file_bytes, filename)
    if preprocessing_mode == "none":
        original_height, original_width = original.shape[:2]
        preprocessed = PreprocessResult(
            image_bgr=original,
            original_width=original_width,
            original_height=original_height,
            warnings=["preprocessing_disabled"],
        )
    else:
        preprocessed = preprocess_image(original)

    engine = get_ocr_engine(preferred_engine)
    page = engine.recognize(preprocessed.image_bgr)
    text = page.plain_text()

    classification = classify_certificate(text, page.width, page.height)
    fields = extract_fields(classification.cert_type, page)
    fields, quality = validate_fields(classification.cert_type, fields)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    warnings = list(preprocessed.warnings) + list(page.warnings)
    actual_engine = (page.engine or "unknown").lower()
    if requested_engine not in {"default", "auto", actual_engine}:
        warnings.append(f"requested OCR engine '{requested_engine}' fell back to '{page.engine}'")
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
        "requestedEngine": requested_engine,
        "actualEngine": page.engine,
        "image": {
            "width": page.width,
            "height": page.height,
            "originalWidth": preprocessed.original_width,
            "originalHeight": preprocessed.original_height,
        },
        "warnings": warnings,
        "processingMs": elapsed_ms,
        "preprocessingMode": preprocessing_mode,
        "version": "document-ai-v2",
    }
