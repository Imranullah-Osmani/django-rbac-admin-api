import csv
import io

from django.core.exceptions import ValidationError


MAX_CSV_IMPORT_BYTES = 1024 * 1024
MAX_CSV_IMPORT_ROWS = 500


def csv_import_too_large(upload, max_bytes: int = MAX_CSV_IMPORT_BYTES) -> bool:
    return bool(getattr(upload, "size", 0) and upload.size > max_bytes)


def csv_import_has_too_many_rows(rows, max_rows: int = MAX_CSV_IMPORT_ROWS) -> bool:
    return len(rows) > max_rows

def read_csv_upload(upload, required_headers: set[str]) -> list[dict[str, str]]:
    try:
        content = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload must be a UTF-8 encoded CSV file.") from exc
    if "\x00" in content:
        raise ValueError("CSV files cannot contain NUL characters.")

    try:
        reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
        headers = reader.fieldnames or []
        missing = required_headers - set(headers)
        if missing:
            raise ValueError(f"Missing required CSV columns: {', '.join(sorted(missing))}.")
        if any(not header.strip() for header in headers) or len(headers) != len(set(headers)):
            raise ValueError("CSV column names must be non-empty and unique.")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row ending at line {reader.line_num} does not match the column count.")
            rows.append(row)
            if len(rows) > MAX_CSV_IMPORT_ROWS:
                raise ValueError("CSV import files can include at most 500 data rows.")
        return rows
    except csv.Error as exc:
        raise ValueError("Upload must contain well-formed CSV data.") from exc


def validate_import_fields(model, values: dict[str, str], row_number: int) -> list[dict]:
    errors = []
    for name, value in values.items():
        try:
            model._meta.get_field(name).clean(value, None)
        except ValidationError as exc:
            errors.append({"row": row_number, "field": name, "detail": " ".join(exc.messages)})
    return errors
