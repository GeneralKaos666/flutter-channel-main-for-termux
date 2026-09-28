# New Repo Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push current `flutter-main-for-termux` branch as `main` of a new empty repo with all hardcoded `GeneralKaos666/flutter-for-termux` URLs migrated.

**Architecture:** Keep full history (`git push <new-remote> flutter-main-for-termux:main`). Sed `OLD_OWNER/OLD_REPO` -> `NEW_OWNER/NEW_REPO` across installers/docs/scripts plus the drift-check regex that rewrites URLs, then run the lightweight verification suite before any push.

**Tech Stack:** git, `scripts/ci/check_version_drift.py` (+ `--fix`), `scripts/ci/check_repo.py`, `test_build.py`, GitHub releases (`.deb` asset flows in `build.yml` / `build-deb.yml`).

**Spec:** This conversation: "create a new empty repo (e.g. `flutter-main-for-termux`), then push this branch as its `main`" with caveats that installers/`DEB_URL`s/docs point at `GeneralKaos666/flutter-for-termux` and drift checks pin those URLs.

## Global Constraints

- `python -m py_compile build.py package.py sysroot.py utils.py scripts/ci/check_repo.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py scripts/ci/generate_versions.py` must pass.
- `pytest test_build.py` must pass (no `tests/` dir; `pytest.ini` testpaths=`test_build.py`).
- `bash -n scripts/install/post_install.sh scripts/test/gh_e2e_test.sh scripts/device/termux_smoke.sh` must pass.
- `python scripts/ci/generate_versions.py --check`, `python scripts/ci/check_version_drift.py`, `python scripts/ci/check_repo.py`, `git diff --check` must pass.
- New docs live under `docs/`; root markdown allowlist enforced by `check_repo.py`.
- Every `.sh` keeps `#!` + LF-only endings; never commit `scratch/`, `*.bak`, `*.receipt.json`, test caches.
- `patches/dart.new.patch` stays a symlink to `patches/dart.patch` — edit `dart.patch` only.
- Do not run `patch_engine/patch_dart/patch_skia` right after `sync` (hooks already applied them).
- Only ARM64 packaging is supported; `build()` ninja target list is contract (asserted by `test_build.py`).

## Review Focus

- Old release links cached on-device/in docs keep downloading from `GeneralKaos666/flutter-for-termux` after migration; users expect the new repo to serve its own releases.
- `check_version_drift.py:95` autofix regex hardcodes the old owner/repo, so a partial sed reintroduces old URLs on next `--fix` run.
- `verify_release_asset.py` defaults `GITHUB_REPOSITORY` to `GeneralKaos666/flutter-for-termux`; CI on the new repo passes via env, but local runs validate the wrong repo.
- `git push <new-remote> flutter-main-for-termux:main` to a non-empty repo with README rejects or creates divergent `main`; new repo must be empty.
- Existing stable release/download links break on move; consumers expect a redirect note or archived pointer in the old repo.

---

### Task 1: Lock new repo coordinates + create empty repo

**Files:**
- Modify: none (decision only)
- Test: `git ls-remote <new-url>` reachable + empty check

**Interfaces:**
- Consumes: current `git remote -v` (`origin=https://github.com/GeneralKaos666/flutter-for-termux.git`), current branch `flutter-main-for-termux` (`git branch --show-current`).
- Produces: `NEW_OWNER`, `NEW_REPO`, `NEW_URL=https://github.com/<NEW_OWNER>/<NEW_REPO>.git` recorded for Tasks 2-4.

- [ ] **Step 1: Confirm new coordinates with user**

Ask: `NEW_OWNER` + `NEW_REPO` (default suggestion `GeneralKaos666/flutter-main-for-termux` per branch name, or new owner if fork/org move). Record exact strings; no defaulting to `flutter-main-for-termux` under old owner without confirmation.
Run: `echo "$NEW_OWNER/$NEW_REPO"` for the record.
Expected: explicit `NEW_OWNER/NEW_REPO` in reply.

- [ ] **Step 2: Create empty repo (no README, no .gitignore, no license)**

Run: `gh repo create <NEW_OWNER>/<NEW_REPO> --public --confirm` OR create via web UI with "Add README" unchecked.
Expected: `git ls-remote https://github.com/<NEW_OWNER>/<NEW_REPO>.git` shows no `refs/heads/main` (empty) or only succeeds without refs.

- [ ] **Step 3: Verify auth can write to new repo**

Run: `git ls-remote https://github.com/<NEW_OWNER>/<NEW_REPO>.git`
Expected: exit 0, empty output (no heads) — proves read; write proven in Task 4 push.

---

### Task 2: Migrate hardcoded `GeneralKaos666/flutter-for-termux` -> `NEW_OWNER/NEW_REPO`

**Files:**
- Modify: `README.md:30,52,66`, `install_flutter_complete.sh:6,30,369,456,1047`, `scripts/install/install.sh`, `scripts/install/install_termux_flutter.sh:6,16,24,133`, `scripts/install/lib_common.sh:25`, `scripts/test/gh_e2e_test.sh:19,24`, `docs/guides/INSTALL_GUIDE.md`, `docs/guides/BUILD_GUIDE.md:165`, `docs/guides/BUILD_PROCESS.md:296`, `docs/releases/RELEASE_NOTES.md:26`, `docs/CI_CD.md:164,265`, `scripts/device/run_termux_smoke.ps1:5`, `scripts/ci/verify_release_asset.py:372`, `scripts/ci/check_version_drift.py:95-96`
- Test: `scripts/ci/check_version_drift.py`, `scripts/ci/check_repo.py`

**Interfaces:**
- Consumes: `NEW_OWNER/NEW_REPO` from Task 1, `OLD=GeneralKaos666/flutter-for-termux`.
- Produces: zero `grep -r GeneralKaos666/flutter-for-termux` hits (except intentional historical notes); drift autofix rewrites to new URLs.

- [ ] **Step 1: Write failing grep proving old URLs remain**

Run: `grep -rn "GeneralKaos666/flutter-for-termux" --exclude-dir=.git --exclude-dir=flutter --exclude-dir=sysroot . | wc -l`
Expected: FAIL-equivalent: count is 28 (current) > 0, proving migration needed.

- [ ] **Step 2: Sed owner/repo across code, docs, workflows**

Run: `grep -rl "GeneralKaos666/flutter-for-termux" --exclude-dir=.git --exclude-dir=flutter --exclude-dir=sysroot . | xargs sed -i "s|GeneralKaos666/flutter-for-termux|<NEW_OWNER>/<NEW_REPO>|g"`
Expected: `grep -rn "GeneralKaos666/flutter-for-termux" --exclude-dir=.git --exclude-dir=flutter --exclude-dir=sysroot .` returns empty. Includes `check_version_drift.py:95` `https://github\.com/GeneralKaos666/flutter-for-termux/releases/download/` pattern and `verify_release_asset.py:372` default.

- [ ] **Step 3: Run drift autofix to normalize any versioned URL shape**

Run: `python scripts/ci/check_version_drift.py --fix; git diff --stat`
Expected: either "Auto-fix made no changes" or only version normalization diffs; no reintroduction of old owner (re-run Step 2 grep to confirm 0 hits).

- [ ] **Step 4: Run drift + repo contracts**

Run: `python scripts/ci/check_version_drift.py && python scripts/ci/check_repo.py`
Expected: PASS (`Version drift check PASSED`, `Repository sanity check passed.`).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(main): migrate repo URLs to <NEW_OWNER>/<NEW_REPO>"
```

---

### Task 3: Lightweight verification (mirrors `ci.yml`)

**Files:**
- Modify: none (verification only)
- Test: `test_build.py`, `scripts/ci/generate_versions.py --check`

**Interfaces:**
- Consumes: migrated tree from Task 2.
- Produces: green gate before push.

- [ ] **Step 1: Compile + unit tests + shell syntax**

Run: `python -m py_compile build.py package.py sysroot.py utils.py scripts/ci/check_repo.py scripts/ci/check_version_drift.py scripts/ci/verify_release_asset.py scripts/ci/generate_versions.py && pytest test_build.py -q && bash -n scripts/install/post_install.sh scripts/test/gh_e2e_test.sh scripts/device/termux_smoke.sh`
Expected: all PASS, no syntax errors.

- [ ] **Step 2: Versions + whitespace**

Run: `python scripts/ci/generate_versions.py --check && git diff --check`
Expected: PASS, no whitespace errors.

---

### Task 4: Push `flutter-main-for-termux` as `main` of new repo

**Files:**
- Modify: git remotes only (no tree change)
- Test: `git ls-remote <NEW_URL>` shows `main` == local HEAD

**Interfaces:**
- Consumes: green tree from Task 3, `NEW_URL` from Task 1, local ref `flutter-main-for-termux` (`cb61e8a` at plan time).
- Produces: new repo `main` == local `flutter-main-for-termux` HEAD with full history; old `origin` untouched.

- [ ] **Step 1: Dry-run push without mutating remotes**

Run: `git push --dry-run <NEW_URL> flutter-main-for-termux:main`
Expected: success message, no rejection (proves empty repo + auth). If rejected non-empty, stop and re-do Task 1 Step 2 with an empty repo.

- [ ] **Step 2: Push history to new repo**

Run: `git push <NEW_URL> flutter-main-for-termux:main`
Expected: `To https://github.com/<NEW_OWNER>/<NEW_REPO>.git * [new branch] flutter-main-for-termux -> main`.

- [ ] **Step 3: Verify new `main` binding**

Run: `git ls-remote <NEW_URL> refs/heads/main` and compare to `git rev-parse flutter-main-for-termux`
Expected: SHAs match; `git log <NEW_URL main> --oneline -3` shows `cb61e8a` chain.

- [ ] **Step 4: Optionally add `new-origin` remote locally (do not replace `origin` yet)**

Run: `git remote add new-origin https://github.com/<NEW_OWNER>/<NEW_REPO>.git; git remote -v`
Expected: `origin` still points at old repo; `new-origin` points at new repo. Do not retarget `origin` until release-workflow destination (`build.yml` publishes to whatever repo it runs in) is confirmed.

- [ ] **Step 5: Decide old-repo pointer (manual, no automation in plan)**

Leave old releases/downloads intact. If clean break desired, add archive note in old repo README after push — separate commit, not part of this push.
Run: none (decision).
Expected: explicit user ack that old `releases/download/...` links now diverge.
