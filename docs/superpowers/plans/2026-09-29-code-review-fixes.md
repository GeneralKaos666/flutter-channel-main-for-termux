# Code-review fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Standards + Spec findings from the `refs/tags/main...HEAD` review while keeping stable per-deb releases.

**Architecture:** Extract version math into one stdlib-only helper imported everywhere; align drift/verify/gate with `Build.release_tag`; keep `prerelease:false` with tag-collision proof; normalize Dart canonical handling; add pinned-REV patch evidence and wire it into `validate.yml` + `main-refresh.yml`.

**Tech Stack:** Python (stdlib `tomllib`, `re`), `utils.py`, `build.py` (Fire), GitHub Actions (`build.yml`, `main-refresh.yml`, `validate.yml`), `scripts/ci/` checks, `test_build.py` (pytest).

**Spec:** `docs/superpowers/plans/2026-09-28-tracking-main.md` (goal: main-tracking deb; architecture: main checkout + channel-aware contracts + gated automation + rebased patches) plus user decisions 2026-09-29: scope=All findings, release visibility=Keep stable (`prerelease:false`, `make_latest:true`).

## Global Constraints

- `python -m py_compile $(git ls-files '*.py' ':!:flutter/*' ':!:sysroot/*')` must pass.
- `pytest test_build.py` must pass (no `tests/` dir; `pytest.ini` names the file).
- `ruff check build.py package.py sysroot.py utils.py test_build.py scripts/ci/` must pass (`ruff format --check` tolerated).
- `bash -n install_flutter_complete.sh $(find scripts -name '*.sh')` must pass.
- `shellcheck --severity=error` on shell scripts must pass.
- `python scripts/ci/generate_versions.py --check`, `python scripts/ci/check_version_drift.py`, `python scripts/ci/check_repo.py`, `git diff --check` must pass.
- New docs live under `docs/`; every `.sh` keeps `#!` + LF-only; never commit `scratch/`, `*.bak`, `*.receipt.json`, test caches.
- `patches/dart.new.patch` stays a symlink to `patches/dart.patch`: edit `dart.patch` only.
- `build()` ninja target list is contract (`flutter`, `flutter/build/archives:artifacts`, `:dart_sdk_archive`, `:flutter_patched_sdk`, `flutter/shell/platform/linux:flutter_gtk`, `flutter/tools/font_subset`).
- Only ARM64 packaging is supported.
- Edits to tracked `.py`/`.sh` get whole-file reformatted by the editing environment: check `git diff --numstat` after each edit and revert unrelated hunks; prefer precise replacements (AGENTS.md Gotcha 11).
- Never hardcode a snapshot-stamped deb name; derive from `build.toml` pins or run drift `--fix`.
- `main` debs use main-distinct names; with Keep-stable decision, `v<upstream>.<YYYYMMDD>.<short>` must provably never collide with stable tags.

## Review Focus

- Gate-computed `release_tag`/`deb_name` drifting from `Build.release_tag`/`Build.output()` on the next pin refresh — expect identical strings from both paths for the same `build.toml`.
- A main snapshot overwriting a stable GitHub `Latest` release — expect `release_guard` to skip publish when the asset exists and the tag shape to never match `vX.Y.Z`.
- `flutter --version --machine` returning `0.0.0-unknown` or a new `frameworkVersion` shape — expect fail-closed abort, not a silent pin bump.
- Dart `3.14.0 (build 3.14.0-271.0.dev)` vs raw `3.14.0-271.0.dev` mismatching README/drift/doctor checks — expect exact canonical match in scripts and semver-extracted match in prose.
- `git apply --check` passing on engine but dart/skia silently rotting — expect pinned-REV evidence naming the probed commit for all three patches.

---

### Task 1: Hygiene — revert reformat noise to minimal diffs

**Files:**
- Modify: `scripts/ci/check_version_drift.py`
- Modify: `scripts/ci/verify_release_asset.py`
- Test: `git diff --numstat`, `git diff --check`

**Interfaces:**
- Consumes: `git diff refs/tags/main...HEAD --numstat` (currently `check_version_drift.py 183/55`, `verify_release_asset.py 341/108` — most is format noise).
- Produces: minimal functional-only hunks in both files; no `rf'\g<1>'` → `rf"\g<1>"` churn, no pure line-wrap splits, no blank-line add/delete.

- [ ] **Step 1: Record current functional hunks**

Run: `git diff refs/tags/main...HEAD -- scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py | grep -E '^@@|snapshot|release_tag|deb_tag|fw_up|BUILD_CRITICAL|allowlist|build.yml' | head -n 60`
Expected: list of hunk headers; functional lines mention snapshot/release_tag/deb logic and build.yml path allowlist.

- [ ] **Step 2: Revert both files to HEAD then re-apply only functional changes with precise replacements**

Run: `git checkout HEAD -- scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py && git status --short`
Expected: clean status for those two paths; subsequent edits use small `oldString` replacements only (no formatter run on the whole file).

- [ ] **Step 3: Re-apply drift functional change only (deb-tag/snapshot mirror + build.yml allowlist) without reformatting neighbors**

Run: `git diff --numstat -- scripts/ci/check_version_drift.py`
Expected: small numbers (e.g. under ~30 added, under ~10 deleted); `git diff --check` clean.

- [ ] **Step 4: Re-apply verify functional change only (per-deb tag/asset resolution) without reformatting neighbors**

Run: `git diff --numstat -- scripts/ci/verify_release_asset.py`
Expected: small numbers relative to the 341/108 before; `git diff --check` clean.

- [ ] **Step 5: Run lightweight checks for both files**

Run: `python -m py_compile scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py && ruff check scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py`
Expected: PASS, no output.

- [ ] **Step 6: Commit**

```bash
git add scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py
git commit -m "chore(ci): keep drift/verify diffs minimal, no reformat noise"
```

### Task 2: Single-source version math (`version_lib.py`)

**Files:**
- Create: `scripts/ci/version_lib.py`
- Modify: `utils.py:27-104` (`snapshot_stamp`, `flutter_to_deb_upstream`, `release_tag`, `deb_version` delegate)
- Modify: `scripts/ci/check_version_drift.py:169-198` (replace inline `_fw_upstream` + stamp with import)
- Modify: `scripts/ci/verify_release_asset.py:302-340` (replace inline mirror with import)
- Modify: `.github/workflows/build.yml:60-115` (gate imports helper instead of mirroring)
- Test: `test_build.py` (new contract test, see Task 3)

**Interfaces:**
- Consumes: `build.toml [flutter] tag, framework_version, framework_revision, framework_commit_date, [package] pkg_rel`.
- Produces: `version_lib.snapshot_stamp(commit_date: str, revision: str) -> str`, `version_lib.flutter_to_deb_upstream(framework_version: str) -> str`, `version_lib.release_tag(framework_version: str, commit_date: str, revision: str) -> str`, `version_lib.deb_version(tag: str, pkg_rel: str, snapshot: str, framework_version: str) -> str`, `version_lib.asset_name(tag: str, pkg_rel: str, snapshot: str, framework_version: str) -> str` (`f"flutter_{deb_version(...)}_aarch64.deb"`, pure stdlib, no `git`/`loguru`/`yaml` imports so Actions + `scripts/ci` can import it via `sys.path` insert of repo root / `scripts/ci`).

- [ ] **Step 1: Write failing contract test pinning gate == Build == drift**

```python
def test_version_single_source_matches_build():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts/ci").resolve()))
    import version_lib
    import build
    b = build.Build()
    assert b.release_tag == version_lib.release_tag(b.framework_version, b.framework_commit_date, b.framework_revision)
    assert b.package_version == version_lib.deb_version(b.tag, b.pkg_rel, b.snapshot, b.framework_version)
```

Run: `pytest test_build.py::test_version_single_source_matches_build -v`
Expected: FAIL with `ModuleNotFoundError: version_lib` / `ImportError`.

- [ ] **Step 2: Create `scripts/ci/version_lib.py` with the five functions moved verbatim from `utils.py:27-104` (stdlib `re` only)**

Run: `python -m py_compile scripts/ci/version_lib.py && python -c "from scripts.ci.version_lib import release_tag; print(release_tag('3.49.0-0.1.pre','2026-09-29 00:17:30 +0000','fab991537bf1ffb063579a0dd8a47cd4f2874618'))"`
Expected: prints `v3.49.0~0.1.pre.20260929.fab9915`.

- [ ] **Step 3: Make `utils.snapshot_stamp`, `utils.flutter_to_deb_upstream`, `utils.release_tag`, `utils.deb_version` thin delegates to `version_lib` (keep signatures + docstrings)**

Run: `python -c "import utils; print(utils.release_tag('3.49.0-0.1.pre','2026-09-29 00:17:30 +0000','fab991537bf1ffb063579a0dd8a47cd4f2874618'))"`
Expected: same `v3.49.0~0.1.pre.20260929.fab9915`; `pytest test_build.py -q` still passes for existing tests.

- [ ] **Step 4: Replace inline mirrors in `check_version_drift.py` and `verify_release_asset.py` with `from version_lib import ...` (add `sys.path` insert for `scripts/ci`; delete local `_fw_upstream`/stamp blocks)**

Run: `grep -rn "_fw_upstream\|Mirror utils" scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py || echo "no mirrors left"`
Expected: prints `no mirrors left`.

- [ ] **Step 5: Replace `build.yml` gate inline Python (lines 78-114) with an import of `version_lib` from the checkout (no pasted `fw_up`/`release_tag` math)**

Run: `grep -n "fw_up\|_b, _r" .github/workflows/build.yml | head`
Expected: no matches in the gate step (only comments referencing `version_lib`).

- [ ] **Step 6: Run the new contract test + drift check**

Run: `pytest test_build.py::test_version_single_source_matches_build -v && python scripts/ci/check_version_drift.py`
Expected: PASS both (`Version drift check PASSED`).

- [ ] **Step 7: Commit**

```bash
git add scripts/ci/version_lib.py utils.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py .github/workflows/build.yml test_build.py
git commit -m "refactor(versions): single-source version_lib for utils, drift, verify, and build gate"
```

### Task 3: Drift `release_tag`/`asset_name` alignment with `Build`

**Files:**
- Modify: `scripts/ci/check_version_drift.py:140-222` (`load_build_config`)
- Test: `test_build.py`

**Interfaces:**
- Consumes: `version_lib.release_tag`, `version_lib.deb_version` (Task 2); `Build.release_tag`, `Build.package_version`, `Build.output('arm64')` (build.py:89-91,282-287).
- Produces: `load_build_config(root) -> dict` where `cfg["release_tag"] == Build().release_tag` and `cfg["asset_name"] == basename(Build().output('arm64'))` for the same `build.toml`; no `release_tag = tag or "main"` fallback.

- [ ] **Step 1: Write the failing alignment test**

```python
def test_drift_config_matches_build_output():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts/ci").resolve()))
    import build
    from check_version_drift import load_build_config
    b = build.Build()
    cfg = load_build_config()
    assert cfg["release_tag"] == b.release_tag
    assert cfg["asset_name"] == b.output("arm64").name
```

Run: `pytest test_build.py::test_drift_config_matches_build_output -v`
Expected: FAIL (currently `cfg["release_tag"] == "main"` vs `v3.49.0~0.1.pre.20260929.fab9915`).

- [ ] **Step 2: Fix `load_build_config` to compute `release_tag` via `version_lib.release_tag(framework_version, framework_commit_date, framework_revision)` and `asset_name` via `version_lib` deb math (same as `Build`)**

Run: `python scripts/ci/check_version_drift.py && python -c "import build; from scripts.ci.check_version_drift import load_build_config; b=build.Build(); c=load_build_config(); print(c['release_tag']==b.release_tag, c['asset_name']==b.output('arm64').name)"`
Expected: drift PASSED and prints `True True`.

- [ ] **Step 3: Run drift autofix + repo contract to catch URL-tag rewrites**

Run: `python scripts/ci/check_version_drift.py --fix && python scripts/ci/check_repo.py && git diff --stat`
Expected: both PASS; diff touches only version-ref files (no unexpected rewrites).

- [ ] **Step 4: Commit**

```bash
git add scripts/ci/check_version_drift.py test_build.py
git commit -m "fix(ci): align drift release_tag/asset with Build.release_tag"
```

### Task 4: Keep-stable release policy — collision proof + guard (user chose Keep stable)

**Files:**
- Modify: `.github/workflows/build.yml:392-401` (keep `prerelease:false`, `make_latest:true`; add comment citing decision)
- Modify: `test_build.py` (tag-collision test)
- Modify: `docs/CI_CD.md` (record intentional Keep-stable per-deb policy + why safe)
- Test: `test_build.py::test_main_release_tag_never_collides_with_stable`

**Interfaces:**
- Consumes: `version_lib.release_tag` (Task 2); gate `release_tag` output; `release_guard` asset-immutability block (`build.yml:341-390`).
- Produces: documented guarantee: main tags match `^v\d+\.\d+\.\d+~.+\.\d{8}\.[0-9a-f]{7}$` or `^vmain\.\d{8}\.[0-9a-f]{7}$`, never `^v?\d+\.\d+\.\d+$`; `release_guard.should_publish=false` when the deb asset already exists.

- [ ] **Step 1: Write the failing collision test**

```python
def test_main_release_tag_never_collides_with_stable():
    import re
    import build
    b = build.Build()
    assert not re.fullmatch(r"v?\d+\.\d+\.\d+", b.release_tag)
    assert re.fullmatch(r"v(\d+\.\d+\.\d+~.+|main)\.\d{8}\.[0-9a-f]{7}", b.release_tag)
```

Run: `pytest test_build.py::test_main_release_tag_never_collides_with_stable -v`
Expected: PASS already (documents current shape); if FAIL, fix `version_lib.release_tag` first.

- [ ] **Step 2: Annotate `build.yml` release block with Keep-stable rationale (per-deb tag is date+hash suffixed, guard preserves immutability, `overwrite_files:false`)**

Run: `grep -n -A3 "prerelease:" .github/workflows/build.yml`
Expected: shows `prerelease: false` + comment `# Keep-stable per 2026-09-29 decision: safe because release_tag ...`.

- [ ] **Step 3: Document the policy + amend the tracking-main plan note (main debs never reuse a stable tag/asset name; stable Latest moves per-deb by design)**

Run: `python scripts/ci/check_version_drift.py && git diff --check`
Expected: drift PASSED (docs use `${TAG}`/`$RELEASE_TAG` vars or derived names, no hardcoded stamped names).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/build.yml test_build.py docs/CI_CD.md
git commit -m "docs(ci): record keep-stable per-deb release policy with collision proof"
```

### Task 5: Dart canonical form (`3.14.0 (build ...)`) end-to-end

**Files:**
- Modify: `scripts/ci/check_version_drift.py:292-322,492-544` (README semver-extract vs canonical exact-match split)
- Modify: `scripts/install/post_install.sh:741,878-916` (keep `CANONICAL_DART_VER` exact canonical + `dart_full_version()` comparison)
- Modify: `scripts/install/flutter_termux_doctor.sh:87,94,109` (keep `EXP_DART` exact canonical)
- Test: `test_build.py` (dart-form test)

**Interfaces:**
- Consumes: `build.toml [flutter] dart_version = '3.14.0 (build 3.14.0-271.0.dev)'` (probe `NEW_DART` from `flutter --version --machine` `dartSdkVersion`).
- Produces: prose checks (`README.md` `Dart SEMVER`) compare extracted semver `3.14.0`; script checks (`CANONICAL_DART_VER`, `EXP_DART`) compare the full canonical string.

- [ ] **Step 1: Write the failing dart-form test**

```python
def test_dart_canonical_vs_prose_forms():
    import re, sys
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts/ci").resolve()))
    from check_version_drift import load_build_config
    cfg = load_build_config()
    assert re.fullmatch(r"\d+\.\d+\.\d+ \(build .+\)", cfg["dart_version"])
    semver = cfg["dart_version"].split(" ")[0]
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", semver)
```

Run: `pytest test_build.py -k dart -v`
Expected: FAIL on the drift README comparison path (exact canonical vs bare semver) until Step 2.

- [ ] **Step 2: Fix drift `check_markdown_docs` README branch to extract leading semver from canonical before comparing; keep `check_post_install_script`/`check_doctor_script` exact-match**

Run: `python scripts/ci/check_version_drift.py`
Expected: `Version drift check PASSED`.

- [ ] **Step 3: Verify on-device comparison helpers unchanged (`dart_full_version()` output format vs `CANONICAL_DART_VER`)**

Run: `bash -n scripts/install/post_install.sh scripts/install/flutter_termux_doctor.sh && grep -n "CANONICAL_DART_VER\|EXP_DART" scripts/install/post_install.sh scripts/install/flutter_termux_doctor.sh`
Expected: no syntax errors; both lines show the parenthesized canonical form.

- [ ] **Step 4: Commit**

```bash
git add scripts/ci/check_version_drift.py test_build.py
git commit -m "fix(ci): split Dart canonical exact-match from prose semver check"
```

### Task 6: Patch-rebase evidence + `validate.yml` wiring

**Files:**
- Create: `scripts/ci/verify_patches.py`
- Create: `patches/last-rebase.txt` (generated, committed per refresh)
- Modify: `.github/workflows/main-refresh.yml:110-125` (call helper, write evidence)
- Modify: `.github/workflows/validate.yml` (run helper on PRs touching `patches/`/`build.toml`/`build.py`/`utils.py`)
- Test: `test_build.py` (helper presence/symlink test already exists; extend with evidence test)

**Interfaces:**
- Consumes: `patches/engine.patch`, `patches/dart.patch`, `patches/skia.patch`; `build.toml [flutter] framework_revision` (pinned REV); shallow `flutter/flutter` checkout at REV.
- Produces: `verify_patches.py --rev <40-hex> [--checkout DIR]` exit 0 + `patches/last-rebase.txt` (`rev=`, `date=`, `engine=OK`, `dart=parse-OK`, `skia=parse-OK`); CI fails closed on conflict.

- [ ] **Step 1: Write the helper contract test (no network)**

```python
def test_verify_patches_helper_exists_and_parses():
    import subprocess
    r = subprocess.run(["python3", "scripts/ci/verify_patches.py", "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "--rev" in r.stdout
```

Run: `pytest test_build.py::test_verify_patches_helper_exists_and_parses -v`
Expected: FAIL (`verify_patches.py` missing).

- [ ] **Step 2: Create `scripts/ci/verify_patches.py` (stdlib only): clone/fetch pinned REV to temp dir when needed, `git apply --check engine.patch`, `git apply --stat` + path-grep for dart (`(pkg|runtime|sdk)/`) and skia (`include/`), write `patches/last-rebase.txt`**

Run: `python scripts/ci/verify_patches.py --help && python -m py_compile scripts/ci/verify_patches.py`
Expected: help prints `--rev`; compile PASS.

- [ ] **Step 3: Run helper against the pinned revision (network; may take minutes)**

Run: `python scripts/ci/verify_patches.py --rev $(python -c "import tomllib; print(tomllib.load(open('build.toml','rb'))['flutter']['framework_revision'])")`
Expected: exit 0, `patches/last-rebase.txt` written with matching `rev=`.

- [ ] **Step 4: Wire helper into `main-refresh.yml` patch-check step and `validate.yml` path-filtered job; commit the evidence file**

Run: `python scripts/ci/check_repo.py && git diff --check`
Expected: PASS (helper listed in CI critical files if `check_repo.py` enforces it; evidence file uses LF).

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/verify_patches.py patches/last-rebase.txt .github/workflows/main-refresh.yml .github/workflows/validate.yml test_build.py
git commit -m "ci(patches): pinned-REV rebase evidence plus validate wiring"
```

### Task 7: Full lightweight verification (mirrors `ci.yml` order)

**Files:**
- Touch: none (verification only; fix fallout in owning task).

**Interfaces:**
- Consumes: all Tasks 1-6 outputs.
- Produces: green suite output recorded in the final commit message or PR body.

- [ ] **Step 1: Compile + unit tests**

Run: `python -m py_compile $(git ls-files '*.py' ':!:flutter/*' ':!:sysroot/*') && pytest test_build.py -q`
Expected: PASS.

- [ ] **Step 2: Lint + shell + version contracts**

Run: `ruff check build.py package.py sysroot.py utils.py test_build.py scripts/ci/ && bash -n install_flutter_complete.sh $(find scripts -name '*.sh') && shellcheck --severity=error install_flutter_complete.sh $(find scripts -name '*.sh' -exec grep -l '^#!/.*\(ba\)\?sh' {} +) && python scripts/ci/generate_versions.py --check && python scripts/ci/check_version_drift.py && python scripts/ci/check_repo.py && git diff --check`
Expected: all PASS (ruff format check tolerated as `|| true` per AGENTS.md).

- [ ] **Step 3: Confirm minimal diffs**

Run: `git diff --numstat | tail -n 15`
Expected: no whole-file blowups; `check_version_drift.py`/`verify_release_asset.py` hunks small after Task 1.
