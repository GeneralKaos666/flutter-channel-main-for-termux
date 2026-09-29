#!/usr/bin/env python3
"""Verify patches against a pinned Flutter framework revision.

Fail-closed rebase evidence used by ``main-refresh.yml`` (probed HEAD) and
``validate.yml`` (pinned ``build.toml`` revision):

- ``engine.patch`` must apply cleanly: ``git apply --check`` inside a
  ``flutter/flutter`` checkout at the pinned revision.
- ``dart.patch`` / ``skia.patch`` apply inside the Dart/Skia repos (fetched
  via ``.gclient`` custom_hooks), which are absent here, so parse-level
  check only: ``git apply --stat`` plus a path-shape grep (same contract as
  ``validate.yml``).

On success writes ``patches/last-rebase.txt`` (``rev=``, ``date=``,
``engine=OK``, ``dart=parse-OK``, ``skia=parse-OK``). Any conflict exits
nonzero with no evidence written. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCHES = {
    "engine": ROOT / "patches" / "engine.patch",
    "dart": ROOT / "patches" / "dart.patch",
    "skia": ROOT / "patches" / "skia.patch",
}
EVIDENCE = ROOT / "patches" / "last-rebase.txt"
FLUTTER_REPO = "https://github.com/flutter/flutter.git"
REV_RE = re.compile(r"[0-9a-f]{40}")
# Parse-level path shapes: dart.patch touches the Dart repo (pkg/runtime/sdk),
# skia.patch touches Skia public headers (include/). Mirrors validate.yml.
STAT_SHAPES = {
    "dart": re.compile(r" (pkg|runtime|sdk)/"),
    "skia": re.compile(r" include/"),
}


def die(message: str) -> int:
    print(f"verify_patches: {message}", file=sys.stderr)
    return 1


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def ensure_checkout(rev: str, checkout: Path | None) -> tuple[Path, Path | None]:
    """Return (checkout_dir, temp_dir_to_cleanup_or_None). Fails closed."""
    if checkout is not None:
        if not (checkout / ".git").exists():
            raise SystemExit(f"--checkout is not a git checkout: {checkout}")
        head = run_git(["rev-parse", "HEAD"], checkout)
        if head.returncode != 0:
            raise SystemExit(f"cannot read HEAD of {checkout}: {head.stderr.strip()}")
        if head.stdout.strip() != rev:
            raise SystemExit(
                f"checkout HEAD {head.stdout.strip()[:12]} != pinned rev {rev[:12]}; "
                "refusing to validate against the wrong revision"
            )
        return checkout, None
    tmp = Path(tempfile.mkdtemp(prefix="flutter-rebase-"))
    try:
        init = run_git(["init", "-q"], tmp)
        if init.returncode != 0:
            raise SystemExit(f"git init failed: {init.stderr.strip()}")
        remote = run_git(["remote", "add", "origin", FLUTTER_REPO], tmp)
        if remote.returncode != 0:
            raise SystemExit(f"git remote add failed: {remote.stderr.strip()}")
        fetch = run_git(["fetch", "--depth", "1", "origin", rev], tmp)
        if fetch.returncode != 0:
            raise SystemExit(f"fetch of pinned rev {rev[:12]} failed: {fetch.stderr.strip()}")
        out = run_git(["checkout", "-q", "FETCH_HEAD"], tmp)
        if out.returncode != 0:
            raise SystemExit(f"checkout of {rev[:12]} failed: {out.stderr.strip()}")
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return tmp, tmp


def check_engine(checkout: Path) -> None:
    missing = [k for k, p in PATCHES.items() if not p.is_file()]
    if missing:
        raise SystemExit(f"missing patch file(s): {', '.join(missing)}")
    r = run_git(["apply", "--check", str(PATCHES["engine"])], checkout)
    if r.returncode != 0:
        raise SystemExit(
            f"engine.patch does not apply cleanly at rev (conflict, fail closed):\n"
            f"{r.stderr.strip() or r.stdout.strip()}"
        )


def check_stat_shape(name: str, checkout: Path) -> None:
    r = run_git(["apply", "--stat", str(PATCHES[name])], checkout)
    if r.returncode != 0:
        raise SystemExit(
            f"{name}.patch failed to parse (fail closed):\n{r.stderr.strip() or r.stdout.strip()}"
        )
    if not r.stdout.strip() or not STAT_SHAPES[name].search(r.stdout):
        raise SystemExit(
            f"{name}.patch stat has unexpected path shape (fail closed):\n{r.stdout.strip()}"
        )


def write_evidence(rev: str) -> None:
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S +0000")
    EVIDENCE.write_text(
        f"rev={rev}\ndate={now}\nengine=OK\ndart=parse-OK\nskia=parse-OK\n",
        encoding="utf-8",
        newline="\n",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify patches apply against a pinned flutter/flutter revision "
        "and record patches/last-rebase.txt evidence (fail closed)."
    )
    parser.add_argument(
        "--rev",
        required=True,
        help="Pinned 40-hex framework revision to validate against.",
    )
    parser.add_argument(
        "--checkout",
        default=None,
        help="Existing flutter/flutter checkout at --rev (saves a clone). "
        "When omitted, the pinned rev is fetched shallowly into a temp dir.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not REV_RE.fullmatch(args.rev):
        return die(f"unexpected --rev (want 40-hex): {args.rev!r}")
    checkout_arg = Path(args.checkout) if args.checkout else None
    try:
        checkout, tmpdir = ensure_checkout(args.rev, checkout_arg)
    except SystemExit as e:
        return die(str(e))
    try:
        try:
            check_engine(checkout)
            check_stat_shape("dart", checkout)
            check_stat_shape("skia", checkout)
        except SystemExit as e:
            return die(str(e))
        write_evidence(args.rev)
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"patches validate OK against {args.rev[:12]}; wrote {EVIDENCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
