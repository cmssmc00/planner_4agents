#!/usr/bin/env python3
"""Researcher-only semantic grader; fixtures stay outside the candidate workspace.

No candidate code is imported into this process. This is ordinary local testing,
not a sandbox or a tamper-proof benchmark. The hidden fixtures are reproducible.
"""
import argparse
import copy
import csv
import io
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["model", "benchmark", "completed_tasks", "successful_tasks",
           "incomplete_tasks", "success_rate", "input_tokens", "output_tokens", "total_tokens"]
INTEGER_COLUMNS = [name for name in COLUMNS if name not in ("model", "benchmark", "success_rate")]


def call(call_id="c1", input_tokens=10, output_tokens=2, cached_input_tokens=0):
    return dict(call_id=call_id, input_tokens=input_tokens, output_tokens=output_tokens,
                cached_input_tokens=cached_input_tokens)


def task(task_id="t1", model="alpha", benchmark="bench", calls=None,
         run_id="r1", status="completed", success=True):
    return dict(schema_version=1, run_id=run_id, task_id=task_id, model=model,
                benchmark=benchmark, status=status,
                success=None if status == "incomplete" else success,
                calls=[call()] if calls is None else calls)


def row(model="", benchmark="", completed=0, successful=0, incomplete=0, inp=0, out=0):
    return dict(model=model, benchmark=benchmark, completed_tasks=completed,
                successful_tasks=successful, incomplete_tasks=incomplete,
                success_rate=successful / completed if completed else None,
                input_tokens=inp, output_tokens=out, total_tokens=inp + out)


def report(rows, grouped=False, invalid=0, duplicates=0):
    return dict(schema_version=1, group_by=["model", "benchmark"] if grouped else [],
                rows=rows, diagnostics=dict(invalid_records=invalid, duplicate_records=duplicates))


def write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def fixtures(base):
    """Expected values are hand-calculated or accumulated during generation.

    This function never reads candidate output and never imports the reference.
    """
    cases = []
    def add(name, input_path, expected, args=(), fmt="json", code=0, output=False,
            error=False, diagnostics_stderr=False):
        cases.append(dict(name=name, input=input_path, expected=expected,
                          args=list(args), format=fmt, code=code, output=output,
                          error=error, diagnostics_stderr=diagnostics_stderr))

    # Manual golden: unique calls consume 30+12+8 input and 5+3+2 output.
    a = task("a", calls=[call("one", 20, 4, 7), call("one", 20, 4, 7), call("two", 10, 1)])
    b = task("b", calls=[call("one", 12, 3)], success=False)
    c = task("c", calls=[call("one", 8, 2, 8)], status="incomplete")
    golden = write_records(base / "golden.jsonl", [a, b, c])
    expected_golden = report([row(completed=2, successful=1, incomplete=1, inp=50, out=10)])
    add("original_cli_manual_golden", golden, expected_golden)
    add("json_output_file", golden, expected_golden, output=True)
    add("csv_output_file", golden, expected_golden, args=["--format", "csv"], fmt="csv", output=True)

    duplicate_dir = base / "duplicates"
    write_records(duplicate_dir / "a.jsonl", [a, b])
    write_records(duplicate_dir / "nested" / "b.jsonl", [a, c, b])
    add("global_dedup_across_nested_files", duplicate_dir,
        report(expected_golden["rows"], duplicates=2))

    runs = write_records(base / "runs.jsonl", [task("same", run_id="r1"),
                         task("same", run_id="r2"), task("other", run_id="r1")])
    add("run_identity_and_reused_call_ids", runs,
        report([row(completed=3, successful=3, inp=30, out=6)]))

    ordered = write_records(base / "ordered.jsonl", [task("z", model="zeta", benchmark="a"),
        task("b", model="alpha", benchmark="b", success=False),
        task("a", model="alpha", benchmark="a", status="incomplete"),
        task("aa", model="alpha", benchmark="a")])
    expected_ordered = report([row("alpha", "a", 1, 1, 1, 20, 4),
                              row("alpha", "b", 1, 0, 0, 10, 2),
                              row("zeta", "a", 1, 1, 0, 10, 2)], grouped=True)
    add("grouped_values_and_sort_order", ordered, expected_ordered, ["--group-by", "model,benchmark"])

    incomplete = write_records(base / "incomplete.jsonl", [task(status="incomplete", calls=[call("x", 4, 3)])])
    add("incomplete_tokens_and_null_rate", incomplete,
        report([row(incomplete=1, inp=4, out=3)]))
    empty = base / "empty"
    empty.mkdir()
    add("empty_directory_overall", empty, report([row()]))
    add("empty_directory_grouped", empty, report([], grouped=True), ["--group-by", "model,benchmark"])

    # Validation covers booleans pretending to be integers and missing fields.
    invalid_records = [{}, [], None, 1]
    mutations = [("schema_version", True), ("schema_version", 2), ("run_id", ""),
                 ("task_id", 3), ("model", None), ("benchmark", ""),
                 ("status", "running"), ("success", 1), ("success", None), ("calls", {})]
    for key, value in mutations:
        item = task()
        item[key] = value
        invalid_records.append(item)
    for key, value in [("input_tokens", True), ("input_tokens", -1), ("output_tokens", 1.5),
                       ("output_tokens", False), ("cached_input_tokens", 11),
                       ("cached_input_tokens", True), ("cached_input_tokens", -1), ("call_id", "")]:
        item = task()
        item["calls"][0][key] = value
        invalid_records.append(item)
    item = task(status="incomplete")
    del item["success"]
    invalid_records.append(item)
    item = task(status="incomplete")
    item["success"] = False
    invalid_records.append(item)
    invalid_records.append(task(calls=[None]))
    missing_tokens = task()
    del missing_tokens["calls"][0]["input_tokens"]
    invalid_records.append(missing_tokens)
    no_cache = task("valid-no-cache", calls=[{"call_id": "x", "input_tokens": 6, "output_tokens": 1}])
    no_cache["extra"] = "ignored"
    invalid_path = write_records(base / "invalid.jsonl", [no_cache] + invalid_records)
    with invalid_path.open("a", encoding="utf-8") as stream:
        stream.write("\n \t\n{broken JSON\n")
    expected_invalid = report([row(completed=1, successful=1, inp=6, out=1)], invalid=len(invalid_records) + 1)
    add("malformed_json_and_schema_types", invalid_path, expected_invalid)

    invalid_duplicate = copy.deepcopy(a)
    invalid_duplicate["calls"][0]["input_tokens"] = -1
    validated = write_records(base / "validate_first.jsonl", [a, invalid_duplicate, a])
    expected_validated = report([row(completed=1, successful=1, inp=30, out=5)], invalid=1, duplicates=1)
    add("validation_before_deduplication", validated, expected_validated)

    quoting = write_records(base / "quoting.jsonl", [task("q", model='m,"quoted"\nline', benchmark="测试,bench"),
                           task("n", model="zero", benchmark="b", status="incomplete", calls=[])])
    quote_expected = report([row('m,"quoted"\nline', "测试,bench", 1, 1, 0, 10, 2),
                             row("zero", "b", 0, 0, 1)], grouped=True)
    add("csv_quoting_unicode_and_null_rate", quoting, quote_expected,
        ["--group-by", "model,benchmark", "--format", "csv"], fmt="csv")
    add("csv_diagnostic_counts_on_stderr", validated, expected_validated,
        ["--format", "csv"], fmt="csv", diagnostics_stderr=True)
    add("missing_input_helpful_failure", base / "not-present.jsonl", None, error=True)

    discovery = base / "discovery"
    write_records(discovery / "nested" / "valid.jsonl", [task(calls=[])])
    (discovery / "ignore.txt").write_text("This is not JSON\n", encoding="utf-8")
    add("recursive_jsonl_discovery", discovery, report([row(completed=1, successful=1)]))

    # Generated ground truth is accumulated from canonical calls as created.
    # Duplicated tasks/calls are inserted afterward, without altering totals.
    rng = random.Random(90210)
    generated_dir = base / "generated"
    canonical = []
    group_counts = {}
    totals = [0, 0, 0, 0, 0]  # completed, successful, incomplete, input, output
    for i in range(137):
        model = ["beta", "alpha", "gamma"][i % 3]
        benchmark = ["appworld", "tau2", "terminal"][rng.randrange(3)]
        is_incomplete = i % 7 == 0
        success = i % 4 != 0
        calls = []
        call_input = call_output = 0
        for j in range(rng.randrange(5)):
            inp = rng.randrange(0, 800)
            out = rng.randrange(0, 160)
            calls.append(call("call-" + str(j), inp, out, rng.randrange(inp + 1)))
            call_input += inp
            call_output += out
        increments = [int(not is_incomplete), int(not is_incomplete and success), int(is_incomplete), call_input, call_output]
        counts = group_counts.setdefault((model, benchmark), [0] * 5)
        for j, increment in enumerate(increments):
            counts[j] += increment
            totals[j] += increment
        if calls and i % 2 == 0:
            calls.insert(0, copy.deepcopy(calls[0]))
        canonical.append(task("task-" + str(i % 53), model, benchmark, calls,
                              run_id="run-" + str(i // 53),
                              status="incomplete" if is_incomplete else "completed", success=success))
    extras = [copy.deepcopy(item) for i, item in enumerate(canonical) if i % 9 == 0]
    write_records(generated_dir / "a.jsonl", canonical[:70] + extras[:7])
    write_records(generated_dir / "nested" / "b.jsonl", canonical[70:] + extras[7:])
    with (generated_dir / "nested" / "b.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{broken\n{}\n\n")
    generated_overall = report([row("", "", *totals)], invalid=2, duplicates=len(extras))
    generated_grouped = report([row(*key, *group_counts[key]) for key in sorted(group_counts)],
                               grouped=True, invalid=2, duplicates=len(extras))
    add("generated_overall_137_tasks", generated_dir, generated_overall)
    add("generated_grouped_137_tasks", generated_dir, generated_grouped, ["--group-by", "model,benchmark"])
    add("generated_csv_137_tasks", generated_dir, generated_grouped,
        ["--group-by", "model,benchmark", "--format", "csv"], fmt="csv", diagnostics_stderr=True)

    strict_cases = []
    for name, source, expected, args, fmt, code in [
        ("strict_invalid_still_emits_report", invalid_path, expected_invalid, ["--strict"], "json", 2),
        ("strict_duplicate_only_success", duplicate_dir, report(expected_golden["rows"], duplicates=2), ["--strict"], "json", 0),
        ("strict_csv_output_file", validated, expected_validated, ["--strict", "--format", "csv"], "csv", 2)]:
        strict_cases.append(dict(name=name, input=source, expected=expected, args=args,
                                 format=fmt, code=code, output=name.endswith("file"), error=False,
                                 diagnostics_stderr=fmt == "csv"))
    return cases, strict_cases


def compare_report(actual, expected):
    errors = []
    if not isinstance(actual, dict):
        return ["JSON root is not an object"]
    if type(actual.get("schema_version")) is not int or actual.get("schema_version") != 1:
        errors.append("schema_version must be integer 1")
    if actual.get("group_by") != expected["group_by"]:
        errors.append("group_by does not match requested grouping")
    diag = actual.get("diagnostics")
    if not isinstance(diag, dict):
        errors.append("diagnostics object is missing")
    else:
        for name, value in expected["diagnostics"].items():
            if type(diag.get(name)) is not int or diag.get(name) != value:
                errors.append("diagnostics.%s: expected %r, got %r" % (name, value, diag.get(name)))
    errors.extend(compare_rows(actual.get("rows"), expected["rows"]))
    return errors


def compare_rows(actual, expected):
    if not isinstance(actual, list):
        return ["rows is not a list"]
    if len(actual) != len(expected):
        return ["row count: expected %d, got %d" % (len(expected), len(actual))]
    errors = []
    for index, (got, wanted) in enumerate(zip(actual, expected)):
        if not isinstance(got, dict):
            errors.append("row %d is not an object" % index)
            continue
        for name in COLUMNS:
            value, target = got.get(name), wanted[name]
            if name == "success_rate":
                correct = value is None if target is None else (
                    type(value) in (int, float) and math.isfinite(value) and abs(value - target) <= 1e-9)
            elif name in INTEGER_COLUMNS:
                correct = type(value) is int and value == target
            else:
                correct = type(value) is str and value == target
            if name not in got or not correct:
                errors.append("row %d.%s: expected %r, got %r" % (index, name, target, value))
    return errors


def parse_csv(text):
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != COLUMNS:
        raise ValueError("CSV columns differ from the required ordered columns")
    rows = []
    for source in reader:
        if None in source or any(value is None for value in source.values()):
            raise ValueError("CSV row has the wrong number of columns")
        item = dict(source)
        for key in INTEGER_COLUMNS:
            item[key] = int(item[key])
        item["success_rate"] = float(item["success_rate"]) if item["success_rate"] else None
        rows.append(item)
    return rows


def run_case(case, command, workspace, base, timeout):
    arguments = command + [str(case["input"])] + case["args"]
    output_path = base / (case["name"] + "." + case["format"])
    if case["output"]:
        arguments += ["--output", str(output_path)]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    errors = []
    result = dict(name=case["name"], passed=False, checks=[], exit_code=None)
    try:
        process = subprocess.run(arguments, cwd=str(workspace), env=env,
                                 capture_output=True, encoding="utf-8", errors="replace",
                                 timeout=timeout)
    except subprocess.TimeoutExpired:
        result["checks"] = ["command exceeded %s-second timeout" % timeout]
        return result
    except OSError as exc:
        result["checks"] = ["could not start command: " + str(exc)]
        return result
    result["exit_code"] = process.returncode
    if case["error"]:
        if process.returncode == 0:
            errors.append("missing input must exit nonzero")
        if not (process.stderr.strip() or process.stdout.strip()):
            errors.append("missing input must produce a helpful error")
    else:
        if process.returncode != case["code"]:
            errors.append("exit code: expected %d, got %d" % (case["code"], process.returncode))
        try:
            payload = output_path.read_text(encoding="utf-8") if case["output"] else process.stdout
            if case["format"] == "json":
                errors.extend(compare_report(json.loads(payload), case["expected"]))
            else:
                errors.extend(compare_rows(parse_csv(payload), case["expected"]["rows"]))
                if case["diagnostics_stderr"]:
                    # Wording is unconstrained; check numeric counts, not labels.
                    # Paired JSON cases check each count's exact association.
                    if not process.stderr.strip():
                        errors.append("CSV with invalid/duplicate records must report diagnostics on stderr")
                    else:
                        numbers = {int(value) for value in re.findall(r"(?<!\d)\d+(?!\d)", process.stderr)}
                        for count in case["expected"]["diagnostics"].values():
                            if count and count not in numbers:
                                errors.append("CSV stderr is missing a required diagnostic count: %d" % count)
        except (OSError, ValueError, TypeError, csv.Error) as exc:
            errors.append("report could not be read: " + str(exc))
    result["passed"] = not errors
    result["checks"] = errors or ["all required values, output structure and exit behavior match"]
    if errors:
        result["stderr_excerpt"] = process.stderr[-1500:]
        result["stdout_excerpt"] = process.stdout[-1000:]
    return result


def evaluate(workspace, stage, reference=False, timeout=20):
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("candidate workspace is not a directory: " + str(workspace))
    if not reference and not (workspace / "agentstats").is_dir():
        raise ValueError("expected agentstats/ in candidate workspace: " + str(workspace))
    command = [sys.executable, str(ROOT / "researcher" / "reference.py")] if reference else [sys.executable, "-m", "agentstats"]
    # OS temporary storage is deliberately outside the handed-out workspace.
    with tempfile.TemporaryDirectory(prefix="planner-probe-eval-") as temporary:
        base = Path(temporary)
        if workspace == base or workspace in base.parents:
            raise ValueError("temporary fixture directory must be outside candidate workspace")
        stage_a, stage_b = fixtures(base)
        cases = stage_a + (stage_b if stage == "B" else [])
        results = [run_case(case, command, workspace, base, timeout) for case in cases]
    passed = sum(item["passed"] for item in results)
    return dict(schema_version=1, evaluator_version="1.0", stage=stage,
                mode="reference" if reference else "candidate", workspace=str(workspace),
                fixture_seed=90210, per_command_timeout_seconds=timeout,
                passed=passed, total=len(results), acceptance_passed=passed == len(results),
                cases=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, help="candidate root containing agentstats/")
    parser.add_argument("--stage", choices=["A", "B"], default="A")
    parser.add_argument("--output", type=Path, help="save the full JSON evaluation report")
    parser.add_argument("--reference", action="store_true", help="calibrate using researcher/reference.py")
    parser.add_argument("--self-check", action="store_true", help="reference must pass, original starter must fail")
    args = parser.parse_args()
    workspace = args.workspace or ROOT / "starter"
    if args.workspace is None and not (args.reference or args.self_check):
        parser.error("--workspace is required when grading a candidate")
    try:
        if args.self_check:
            reference = evaluate(ROOT, args.stage, reference=True)
            baseline = evaluate(workspace, args.stage)
            success = reference["acceptance_passed"] and not baseline["acceptance_passed"]
            result = dict(mode="self-check", self_check_passed=success,
                          reference=reference, baseline=baseline)
        else:
            result = evaluate(ROOT if args.reference else workspace, args.stage, args.reference)
            success = result["acceptance_passed"]
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        print(payload, end="")
        return 0 if success else 1
    except (OSError, ValueError) as exc:
        print("evaluate: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
