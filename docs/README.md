# Documentation

This directory keeps project documentation out of the repository root while
leaving only the entry-point files there (`README.md`, `AGENTS.md`,
plus the optional `ORIGINAL_REQUEST.md` / `PROJECT.md` allowlisted by
`scripts/ci/check_repo.py`).

## Operations

- [CI/CD and device lab](CI_CD.md) — GitHub Actions workflow map, runner setup, and local equivalents.

## Guides

- [Install guide](guides/INSTALL_GUIDE.md) — Termux install flow and runtime prerequisites.
- [Build guide](guides/BUILD_GUIDE.md) — end-to-end build commands, troubleshooting, and packaging notes.
- [Build process](guides/BUILD_PROCESS.md) — historical build steps and process notes.
- [Upgrade guide](guides/UPGRADE_GUIDE.md) — checklist for moving to a new Flutter release.
- [AAPT2 release build analysis](guides/AAPT2_RELEASE_BUILD_BUG_ANALYSIS.md) — resource stripping root cause, Mode A workaround, and Mode B plan.

## Releases

- [Changelog](releases/CHANGELOG.md) — version history and notable fixes.
- [Release notes](releases/RELEASE_NOTES.md) — notes used for the current GitHub release body.
