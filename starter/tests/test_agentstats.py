import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agentstats.records import read_records, valid_record
from agentstats.report import summarize


def sample(task_id="task-1", status="completed", success=True):
    return {
        "schema_version": 1, "run_id": "run-1", "task_id": task_id,
        "model": "model-a", "benchmark": "mini-eval", "status": status,
        "success": success,
        "calls": [{"call_id": "request-1", "input_tokens": 100,
                   "output_tokens": 20}],
    }


class AgentStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "input.jsonl"

    def write_records(self, records):
        self.path.write_text("".join(json.dumps(row) + "\n" for row in records),
                             encoding="utf-8")

    def report(self):
        return summarize(*read_records(self.path))

    def test_original_cli_and_single_completed_task(self):
        self.write_records([sample()])
        result = subprocess.run(
            [sys.executable, "-m", "agentstats", str(self.path)],
            text=True, capture_output=True, check=True,
        )
        report = json.loads(result.stdout)
        self.assertEqual(report["group_by"], [])
        self.assertEqual(report["rows"][0]["total_tokens"], 120)
        self.assertEqual(report["rows"][0]["success_rate"], 1.0)

    def test_failure_counts_in_denominator_and_incomplete_consumes_tokens(self):
        self.write_records([
            sample("pass"), sample("fail", success=False),
            sample("partial", status="incomplete", success=None),
        ])
        row = self.report()["rows"][0]
        self.assertEqual((row["completed_tasks"], row["incomplete_tasks"]), (2, 1))
        self.assertEqual(row["success_rate"], 0.5)
        self.assertEqual(row["total_tokens"], 360)

    def test_empty_file_still_has_overall_row(self):
        self.write_records([])
        report = self.report()
        self.assertEqual(len(report["rows"]), 1)
        self.assertIsNone(report["rows"][0]["success_rate"])
        self.assertEqual(report["rows"][0]["total_tokens"], 0)

    def test_invalid_rows_skipped_but_blank_lines_ignored(self):
        self.path.write_text("\n" + json.dumps(sample()) + "\n{broken\n{}\n",
                             encoding="utf-8")
        report = self.report()
        self.assertEqual(report["diagnostics"]["invalid_records"], 2)
        self.assertEqual(report["rows"][0]["completed_tasks"], 1)

    def test_boolean_token_count_is_not_integer_token_count(self):
        record = sample()
        record["calls"][0]["input_tokens"] = True
        self.assertFalse(valid_record(record))

    def test_original_output_option(self):
        self.write_records([sample()])
        destination = Path(self.temp.name) / "report.json"
        result = subprocess.run(
            [sys.executable, "-m", "agentstats", str(self.path),
             "--output", str(destination)], text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(destination.read_text())["schema_version"], 1)

    def test_cached_input_regression(self):
        record = sample()
        record["calls"][0]["cached_input_tokens"] = 60
        self.write_records([record])
        row = self.report()["rows"][0]
        self.assertEqual(row["input_tokens"], 100)
        self.assertEqual(row["total_tokens"], 120)

    def test_repeated_call_regression(self):
        record = sample()
        record["calls"].append(copy.deepcopy(record["calls"][0]))
        self.write_records([record])
        self.assertEqual(self.report()["rows"][0]["total_tokens"], 120)

    def test_repeated_record_regression(self):
        record = sample()
        self.write_records([record, copy.deepcopy(record)])
        report = self.report()
        self.assertEqual(report["diagnostics"]["duplicate_records"], 1)
        self.assertEqual(report["rows"][0]["completed_tasks"], 1)
        self.assertEqual(report["rows"][0]["total_tokens"], 120)


if __name__ == "__main__":
    unittest.main()
