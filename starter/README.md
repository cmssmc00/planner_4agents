# agentstats

A small Python utility for summarizing LLM agent evaluation logs. It uses only
the Python standard library and runs on Python 3.10 or newer on Linux/macOS.

The existing command produces an overall JSON summary. Some reported totals
are incorrect. The requested repair and reporting enhancements are specified
in **TASK.md**, which is the source of truth for expected behavior.

From this directory, run:

```bash
python -m agentstats fixtures
python -m agentstats fixtures --output report.json
python -m unittest discover -s tests -v
```

No package installation or network access is required. Use `python3` if that
is the name of your Python 3 interpreter.

## Project contents

- `agentstats/`: input validation, aggregation, and command-line interface.
- `tests/`: public behavior and regression tests.
- `fixtures/`: sample logs spread across several files and directories.
- `TASK.md`: requested behavior, format contract, and acceptance criteria.

Sample logs include completed and incomplete runs and multiple model/benchmark
pairs. They use synthetic names and counts; no credentials or real user data
are included. The public tests are useful checks, but do not exhaust all of
the requirements in TASK.md.
