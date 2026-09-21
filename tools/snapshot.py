#!/usr/bin/env python3
"""Save the complete current workspace (including new files) for a study stage."""
import argparse
from pathlib import Path
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not workspace.is_dir():
        parser.error("Workspace must be a directory.")
    if output.exists():
        parser.error("Output exists; use a different output name.")
    if output.is_relative_to(workspace):
        parser.error("Write the snapshot outside the workspace (for example in ../records/).")
    output.parent.mkdir(parents=True, exist_ok=True)
    skipped = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(workspace.rglob("*")):
            rel = path.relative_to(workspace)
            if path.is_file() and not path.is_symlink() and not any(part in skipped for part in rel.parts):
                archive.write(path, "workspace/" + rel.as_posix())
        for filename, command in (
            ("tracked_changes.patch", ["git", "diff", "HEAD", "--"]),
            ("git_status.txt", ["git", "status", "--short"]),
        ):
            result = subprocess.run(command, cwd=workspace, capture_output=True, text=True)
            archive.writestr(filename, result.stdout if result.returncode == 0 else result.stderr)
    print(output)


if __name__ == "__main__":
    main()
