"""Command-line entry point."""

import argparse
import json
import sys
from pathlib import Path

from .records import read_records
from .report import summarize


def parser():
    result = argparse.ArgumentParser(
        description="Summarize agent evaluation logs."
    )
    result.add_argument("input", help="JSONL file or directory")
    result.add_argument("--output", help="Write the JSON report to this file")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        records, diagnostics = read_records(args.input)
        report = summarize(records, diagnostics)
        rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        if diagnostics["invalid_records"]:
            print("Skipped {} invalid record(s).".format(
                diagnostics["invalid_records"]), file=sys.stderr)
    except (OSError, UnicodeError) as error:
        print("agentstats: {}".format(error), file=sys.stderr)
        return 1
    return 0
