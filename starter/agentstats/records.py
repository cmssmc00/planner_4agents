"""Read and validate the version 1 interchange format."""

import json
from pathlib import Path


def _nonnegative_integer(value):
    return type(value) is int and value >= 0


def _nonempty_string(value):
    return isinstance(value, str) and bool(value)


def valid_record(record):
    if not isinstance(record, dict):
        return False
    if type(record.get("schema_version")) is not int:
        return False
    if record["schema_version"] != 1:
        return False
    if not all(_nonempty_string(record.get(key)) for key in
               ("run_id", "task_id", "model", "benchmark")):
        return False
    status = record.get("status")
    if status not in ("completed", "incomplete"):
        return False
    if "success" not in record:
        return False
    if status == "completed" and type(record["success"]) is not bool:
        return False
    if status == "incomplete" and record["success"] is not None:
        return False
    calls = record.get("calls")
    if not isinstance(calls, list):
        return False
    for call in calls:
        if not isinstance(call, dict):
            return False
        if not _nonempty_string(call.get("call_id")):
            return False
        if not _nonnegative_integer(call.get("input_tokens")):
            return False
        if not _nonnegative_integer(call.get("output_tokens")):
            return False
        cached = call.get("cached_input_tokens", 0)
        if not _nonnegative_integer(cached):
            return False
        if cached > call["input_tokens"]:
            return False
    return True


def input_files(source):
    source = Path(source)
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(
            source.rglob("*.jsonl"),
            key=lambda path: path.relative_to(source).as_posix(),
        )
    raise OSError("Input does not exist or is not a file/directory: {}".format(source))


def read_records(source):
    """Return valid rows and input-wide diagnostics."""
    records = []
    diagnostics = {"invalid_records": 0, "duplicate_records": 0}
    for path in input_files(source):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except (ValueError, TypeError):
                    diagnostics["invalid_records"] += 1
                    continue
                if not valid_record(record):
                    diagnostics["invalid_records"] += 1
                    continue
                records.append(record)
    return records, diagnostics
