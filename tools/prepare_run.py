#!/usr/bin/env python3
"""Create one independent agent workspace; never overwrite an existing run."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=["claude", "codex", "deepseek", "qoder"], required=True)
    parser.add_argument("--trial", type=int, default=1)
    parser.add_argument("--runs-root", type=Path, default=Path.home() / "planner_probe_runs")
    parser.add_argument("--condition", choices=["natural", "plan"], default="natural")
    args = parser.parse_args()
    if args.trial < 1:
        parser.error("--trial must be at least 1")
    if not shutil.which("git"):
        parser.error("Git is required. Install Git, then run this command again.")
    bundle = Path(__file__).resolve().parents[1]
    starter = bundle / "starter"
    run = args.runs_root.expanduser().resolve() / args.system / f"{args.condition}_{args.trial:02d}"
    if run.exists():
        parser.error(f"Refusing to overwrite an existing run: {run}. Choose another --trial.")
    if not (starter / "TASK.md").is_file():
        parser.error("starter/TASK.md is missing; extract the complete ZIP first.")
    run.mkdir(parents=True)
    workspace = run / "workspace"
    records = run / "records"
    records.mkdir()
    shutil.copytree(starter, workspace, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    try:
        for command in (
            ["git", "init", "--quiet"],
            ["git", "add", "."],
            ["git", "-c", "user.name=Planner Probe", "-c", "user.email=probe@example.invalid",
             "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Pristine Planner Probe v1 task"],
        ):
            subprocess.run(command, cwd=workspace, check=True, capture_output=True, text=True)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    except subprocess.CalledProcessError as exc:
        print(f"Git setup failed: {exc.stderr or exc}. Partial run retained at {run}", file=sys.stderr)
        return 1
    meta = {
        "experiment": "planner_probe_v1", "system": args.system,
        "trial": args.trial, "condition": args.condition,
        "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace), "baseline_commit": commit,
        "starter_sha256": tree_hash(starter),
        "task_sha256": hashlib.sha256((starter / "TASK.md").read_bytes()).hexdigest(),
        "python_version": sys.version.split()[0],
        "system_version": None, "backend_model": None, "reasoning_effort": None,
        "extensions_or_skills": [], "permission_settings": None,
        "user_or_project_instructions": None, "tool_access": None,
        "budget_minutes": 30, "started_utc": None, "ended_utc": None,
        "stop_reason": None, "human_interventions": [],
        "usage": {"input_tokens": None, "cached_input_tokens": None,
                  "output_tokens": None, "reasoning_tokens": None,
                  "scope_and_source": None},
        "note": "Null means not recorded or unavailable; never replace unavailable values with zero.",
    }
    (records / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ("observations.csv", "run_notes.md"):
        template = bundle / "researcher" / name
        if template.exists():
            shutil.copyfile(template, records / name)
    print(json.dumps({"workspace": str(workspace), "records": str(records),
                      "task": str(workspace / "TASK.md"), "baseline_commit": commit},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
