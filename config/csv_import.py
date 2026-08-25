MAX_CSV_IMPORT_BYTES = 1024 * 1024


def csv_import_too_large(upload, max_bytes: int = MAX_CSV_IMPORT_BYTES) -> bool:
    return bool(getattr(upload, "size", 0) and upload.size > max_bytes)
