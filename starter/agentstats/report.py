"""Aggregate validated logs into a machine-readable report."""


def empty_row():
    return {
        "model": "",
        "benchmark": "",
        "completed_tasks": 0,
        "successful_tasks": 0,
        "incomplete_tasks": 0,
        "success_rate": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def summarize(records, diagnostics):
    row = empty_row()
    for record in records:
        if record["status"] == "completed":
            row["completed_tasks"] += 1
            row["successful_tasks"] += int(record["success"])
        else:
            row["incomplete_tasks"] += 1
        for call in record["calls"]:
            row["input_tokens"] += (
                call["input_tokens"] + call.get("cached_input_tokens", 0)
            )
            row["output_tokens"] += call["output_tokens"]
    if row["completed_tasks"]:
        row["success_rate"] = row["successful_tasks"] / row["completed_tasks"]
    row["total_tokens"] = row["input_tokens"] + row["output_tokens"]
    return {
        "schema_version": 1,
        "group_by": [],
        "rows": [row],
        "diagnostics": dict(diagnostics),
    }
