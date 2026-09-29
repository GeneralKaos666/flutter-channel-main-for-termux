#!/usr/bin/env python3
"""Single-source Flutter version math (stdlib only).

Shared by utils.py, scripts/ci checks, and the build.yml gate so the
snapshot stamp, Debian upstream translation, release tag, deb version,
and asset name can never drift apart. Pure stdlib (re only) so Actions
and scripts/ci can import it via a sys.path insert.
"""

import re


def snapshot_stamp(commit_date: str, revision: str) -> str:
    """Monotonic snapshot stamp 'YYYYMMDD.shorthash' from build.toml pins.

    Every main refresh moves the date forward, so each snapshot deb
    version-sorts strictly above the previous one and dpkg/apt can never
    see a new build as a downgrade.
    """
    day = re.split(r"[ T]", str(commit_date).strip(), maxsplit=1)[0].replace("-", "")
    short = str(revision).strip()[:7]
    if not day or not short:
        return ""
    return f"{day}.{short}"


def flutter_to_deb_upstream(framework_version: str) -> str:
    """Translate a Flutter framework version to a Debian upstream version.

    Flutter pre-releases use hyphens ('3.47.6-0.0.pre-123'); Debian uses
    tilde so pre-releases sort below the final ('3.47.6~0.0.pre.123' <
    '3.47.6') while still sorting above the previous stable ('3.47.5').
    Returns '' for missing/'0.0.0-unknown' so callers can fall back.
    """
    fw = str(framework_version or "").strip()
    if not fw or fw == "0.0.0-unknown":
        return ""
    if "-" in fw:
        base, rest = fw.split("-", 1)
        return f"{base}~{rest.replace('-', '.')}"
    return fw


def release_tag(framework_version: str, commit_date: str, revision: str = "") -> str:
    """Short stable GitHub release tag 'v<upstream>.<YYYYMMDD>.<shorthash>'.

    Keeps the .deb full (deb_version) for dpkg monotonicity while the
    GitHub release uses a short human tag, e.g. framework
    '3.49.0-0.1.pre' + '2026-09-29 ...' + 'fab9915...' ->
    'v3.49.0~0.1.pre.20260929.fab9915'.
    Falls back to date-only or version-only when a pin is missing.
    """
    fw = flutter_to_deb_upstream(framework_version)
    day = re.split(r"[ T]", str(commit_date or "").strip(), maxsplit=1)[0].replace("-", "")
    short = str(revision or "").strip()[:7]
    if fw and day and short:
        return f"v{fw}.{day}.{short}"
    if fw and day:
        return f"v{fw}.{day}"
    if fw and short:
        return f"v{fw}.{short}"
    if fw:
        return f"v{fw}"
    if day and short:
        return f"vmain.{day}.{short}"
    if day:
        return "vmain." + day
    return ""


def deb_version(tag: str, pkg_rel: str, snapshot: str = "", framework_version: str = "") -> str:
    """Debian-policy package version for a Flutter tag.

    dpkg requires the version to start with a digit. Semver tags pass
    through as '{tag}-{rel}'. For branch names such as 'main', the
    framework version from `flutter --version --machine` (e.g.
    '3.47.6-0.0.pre-123', the next pre-release past the last stable per
    flutter_tools version.dart) is translated to Debian tilde form and
    suffixed with the snapshot stamp ('3.47.6~0.0.pre.123+main.20260926.
    8db5526-1') so main snapshots sort above the last stable but below
    the next final. Without a framework version it falls back to the
    legacy '0~main.20260926.8db5526-1' (lower than any stable).
    """
    tag, rel, snap = str(tag), str(pkg_rel or "").strip(), str(snapshot or "").strip()
    if tag[:1].isdigit():
        base = tag
    else:
        fw = flutter_to_deb_upstream(framework_version)
        if fw:
            base = fw + (f"+main.{snap}" if snap else "")
        else:
            base = f"0~{tag}" + (f".{snap}" if snap else "")
    return f"{base}-{rel}" if rel else base


def asset_name(tag: str, pkg_rel: str, snapshot: str = "", framework_version: str = "") -> str:
    """Deb filename for a Flutter tag, e.g. 'flutter_<deb_version>_aarch64.deb'."""
    return f"flutter_{deb_version(tag, pkg_rel, snapshot, framework_version)}_aarch64.deb"
