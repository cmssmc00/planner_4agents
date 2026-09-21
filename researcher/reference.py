#!/usr/bin/env python3
"""Independent research calibration oracle. Never copy into agent workspaces."""
import argparse
import csv
import json
import os
from pathlib import Path
import sys


COLUMNS = ["model", "benchmark", "completed_tasks", "successful_tasks",
           "incomplete_tasks", "success_rate", "input_tokens", "output_tokens",
           "total_tokens"]


def nonnegative_integer(value):
    return type(value) is int and value >= 0


def valid_record(record):
    if not isinstance(record, dict):
        return False
    if type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        return False
    if any(not isinstance(record.get(key), str) or not record[key]
           for key in ("run_id", "task_id", "model", "benchmark")):
        return False
    status = record.get("status")
    if status == "completed":
        if type(record.get("success")) is not bool:
            return False
    elif status == "incomplete":
        if "success" not in record or record["success"] is not None:
            return False
    else:
        return False
    calls = record.get("calls")
    if not isinstance(calls, list):
        return False
    for call in calls:
        if not isinstance(call, dict):
            return False
        if not isinstance(call.get("call_id"), str) or not call["call_id"]:
            return False
        if not all(nonnegative_integer(call.get(key))
                   for key in ("input_tokens", "output_tokens")):
            return False
        cache = call.get("cached_input_tokens", 0)
        if not nonnegative_integer(cache) or cache > call["input_tokens"]:
            return False
    return True


def input_paths(path):
    if not path.exists():
        raise OSError("input does not exist: " + str(path))
    if path.is_file():
        return [path]
    if path.is_dir():
        def raise_walk_error(error):
            raise error
        found = []
        for directory, _, filenames in os.walk(path, onerror=raise_walk_error):
            found.extend(Path(directory) / name for name in filenames if name.endswith(".jsonl"))
        return sorted(found, key=lambda item: item.relative_to(path).as_posix())
    raise OSError("input must be a file or directory: " + str(path))


def make_row(model="", benchmark=""):
    return dict(model=model, benchmark=benchmark, completed_tasks=0,
                successful_tasks=0, incomplete_tasks=0, success_rate=None,
                input_tokens=0, output_tokens=0, total_tokens=0)


def summarize(path, grouped):
    unique = {}
    invalid = duplicates = 0
    for source in input_paths(path):
        with source.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    invalid += 1
                    continue
                if not valid_record(record):
                    invalid += 1
                    continue
                identity = (record["run_id"], record["task_id"])
                if identity in unique:
                    duplicates += 1
                else:
                    unique[identity] = record
    rows = {} if grouped else {( "", ""): make_row()}
    for record in unique.values():
        key = (record["model"], record["benchmark"]) if grouped else ("", "")
        row = rows.setdefault(key, make_row(*key))
        if record["status"] == "completed":
            row["completed_tasks"] += 1
            row["successful_tasks"] += int(record["success"])
        else:
            row["incomplete_tasks"] += 1
        calls = {call["call_id"]: call for call in record["calls"]}
        row["input_tokens"] += sum(call["input_tokens"] for call in calls.values())
        row["output_tokens"] += sum(call["output_tokens"] for call in calls.values())
    for row in rows.values():
        count = row["completed_tasks"]
        row["success_rate"] = row["successful_tasks"] / count if count else None
        row["total_tokens"] = row["input_tokens"] + row["output_tokens"]
    return {"schema_version": 1,
            "group_by": ["model", "benchmark"] if grouped else [],
            "rows": [rows[key] for key in sorted(rows)],
            "diagnostics": {"invalid_records": invalid, "duplicate_records": duplicates}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--group-by", choices=["overall", "model,benchmark"], default="overall")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        report = summarize(args.input, args.group_by == "model,benchmark")
        stream = args.output.open("w", encoding="utf-8", newline="") if args.output else sys.stdout
        try:
            if args.format == "json":
                json.dump(report, stream, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
            else:
                writer = csv.DictWriter(stream, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(report["rows"])
        finally:
            if args.output:
                stream.close()
        diag = report["diagnostics"]
        if any(diag.values()):
            print("invalid_records={invalid_records} duplicate_records={duplicate_records}".format(**diag),
                  file=sys.stderr)
        return 2 if args.strict and diag["invalid_records"] else 0
    except (OSError, UnicodeError) as exc:
        print("agentstats: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
