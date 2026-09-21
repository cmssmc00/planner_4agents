# Repair and extend agentstats

The project summarizes LLM agent evaluation logs. Some token totals are
incorrect. Fix the reporting behavior, add reports grouped by model and
benchmark, and add CSV export. Preserve the original command and add useful
tests for your changes. The finished tool must satisfy the contract below.

Use Python 3.10 or newer and the standard library only. No network access or
extra dependencies are required. Preserve the sample log files as input data.

## Input format

The input is a UTF-8 JSONL file or directory. For a directory, recursively read
all `*.jsonl` files, sorted by relative POSIX path, and process lines in file
order. Ignore blank lines. Each malformed JSON or schema-invalid nonblank line
counts as one `invalid_record`; skip it without crashing normal execution.
Ignore extra keys in JSON objects.

Every valid record must contain:

| Field | Required value |
| --- | --- |
| `schema_version` | Integer `1`; a boolean is invalid |
| `run_id`, `task_id`, `model`, `benchmark` | Nonempty strings |
| `status` | `"completed"` or `"incomplete"` |
| `success` | Boolean for completed tasks; `null` for incomplete tasks |
| `calls` | A list of call objects; an empty list is allowed |

Every call object must contain a nonempty string `call_id` and nonnegative
integer `input_tokens` and `output_tokens`. Its optional `cached_input_tokens`
defaults to zero and must be a nonnegative integer no greater than
`input_tokens`. Booleans are not valid integers in any token field.

## Counting rules

- A task is identified by `(run_id, task_id)`. Count a valid task record once
  across the whole input, including across different files. Every extra valid
  occurrence increments `duplicate_records` by one. Duplicate task records
  agree on meaningful fields; handling conflicting duplicates is out of scope.
- Validate records before deduplicating them. An invalid record sharing a task
  identity with a valid record still increments `invalid_records`.
- Within a task, repeated `call_id` values identify the same call. Count each
  call once. Such copies agree on meaningful fields. The same `call_id` in two
  different tasks refers to two different calls.
- Each call's `input_tokens` **already includes** `cached_input_tokens`.
- Include consumed tokens from both completed and incomplete tasks. Sum each
  call once per unique task. Tasks with different `run_id` values are distinct.
- `completed_tasks` counts unique completed tasks, including unsuccessful ones.
  `successful_tasks` counts successful completed tasks. `incomplete_tasks`
  counts unique incomplete tasks.
- `success_rate = successful_tasks / completed_tasks`, expressed as a number
  from zero to one. If there are no completed tasks, the rate is undefined.
- `total_tokens = input_tokens + output_tokens`.

These counts are defined solely by the fields above. Do not infer unrecorded
reasoning tokens or provider-specific token categories.

## Required command line

```text
python -m agentstats INPUT [--group-by overall|model,benchmark] [--format json|csv] [--output PATH]
```

The defaults are `--group-by overall`, `--format json`, and output to stdout.
The existing `python -m agentstats INPUT` and `--output PATH` usages must keep
working. `--output` writes UTF-8 to the specified path; stdout may be empty in
that case. The output's parent directory must already exist. Missing or
unreadable input must produce a helpful error and a nonzero exit code.
Warnings may go to stderr, but must never corrupt machine-readable stdout.

### JSON

The output envelope has this shape (the values here are illustrative):

```json
{
  "schema_version": 1,
  "group_by": [],
  "rows": [
    {
      "model": "",
      "benchmark": "",
      "completed_tasks": 2,
      "successful_tasks": 1,
      "incomplete_tasks": 1,
      "success_rate": 0.5,
      "input_tokens": 50,
      "output_tokens": 10,
      "total_tokens": 60
    }
  ],
  "diagnostics": {"invalid_records": 0, "duplicate_records": 0}
}
```

- Overall reports have `group_by: []` and exactly one row. `model` and
  `benchmark` are empty strings in that row, including for empty input.
- Grouped reports have `group_by: ["model", "benchmark"]` and one row for each
  pair represented by valid tasks. Sort rows by model, then benchmark, in
  ascending order. Empty input produces `rows: []`.
- Counts and token totals are integers. Rates are numbers, or `null` when
  undefined. Floating-point rate differences up to `1e-9` are acceptable.
- Diagnostics count invalid and duplicate records across the complete input,
  not separately within each group.
- Additional JSON fields are allowed.

### CSV

Use these columns in this exact order:

```text
model,benchmark,completed_tasks,successful_tasks,incomplete_tasks,success_rate,input_tokens,output_tokens,total_tokens
```

Use the same rows, sorting, and numeric meaning as JSON. An undefined rate is
an empty cell. CSV contains no diagnostics columns; report nonzero diagnostic
counts on stderr. Quote commas, double quotes, and newlines in names according
to normal CSV conventions.

## Expected result

The corrected tool should handle the documented edge cases, preserve original
CLI behavior, produce consistent JSON and CSV reports, and have meaningful
tests covering the changes. Report what changed and what you verified when
you finish.
