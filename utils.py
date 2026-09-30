import inspect
import os
import re
from functools import wraps

import git
from loguru import logger

from scripts.ci.version_lib import (
    deb_version as _lib_deb_version,
)
from scripts.ci.version_lib import (
    flutter_to_deb_upstream as _lib_fw_upstream,
)
from scripts.ci.version_lib import (
    release_tag as _lib_release_tag,
)
from scripts.ci.version_lib import (
    snapshot_stamp as _lib_snapshot_stamp,
)

__ARCH__ = dict(arm="arm", arm64="aarch64", x64="x86_64", x86="i686")
__MODE__ = ("release", "debug", "profile")

if os.environ.get("PREFIX") == "/data/data/com.termux/files/usr":
    __TERMUX__ = "true"
else:
    __TERMUX__ = "false"


def termux_arch(arch: str):
    if arch in __ARCH__:
        return __ARCH__[arch]
    if arch in __ARCH__.values():
        return arch

    raise ValueError(f'unknown arch: "{arch}"')


def snapshot_stamp(commit_date: str, revision: str) -> str:
    """Monotonic snapshot stamp 'YYYYMMDD.shorthash' from build.toml pins.

    Every main refresh moves the date forward, so each snapshot deb
    version-sorts strictly above the previous one and dpkg/apt can never
    see a new build as a downgrade.
    """
    return _lib_snapshot_stamp(commit_date, revision)


def flutter_to_deb_upstream(framework_version: str) -> str:
    """Translate a Flutter framework version to a Debian upstream version.

    Flutter pre-releases use hyphens ('3.47.6-0.0.pre-123'); Debian uses
    tilde so pre-releases sort below the final ('3.47.6~0.0.pre.123' <
    '3.47.6') while still sorting above the previous stable ('3.47.5').
    Returns '' for missing/'0.0.0-unknown' so callers can fall back.
    """
    return _lib_fw_upstream(framework_version)


def release_tag(framework_version: str, commit_date: str, revision: str = "") -> str:
    """Short stable GitHub release tag 'v<upstream>.<YYYYMMDD>.<shorthash>'.

    Keeps the .deb full (deb_version) for dpkg monotonicity while the
    GitHub release uses a short human tag, e.g. framework
    '3.49.0-0.1.pre' + '2026-09-29 ...' + 'fab9915...' ->
    'v3.49.0-0.1.pre.20260929.fab9915'.
    Falls back to date-only or version-only when a pin is missing.
    """
    return _lib_release_tag(framework_version, commit_date, revision)


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
    return _lib_deb_version(tag, pkg_rel, snapshot, framework_version)


def target_output(root: str, arch: str, mode: str, opted: bool = True):
    root = os.path.abspath(os.path.expanduser(root))
    if opted:
        dest = f"linux_{mode}_{arch}"
    else:
        dest = f"linux_{mode}_unopt_{arch}"
    return os.path.join(root, "engine", "src", "out", dest)


def flutter_tag(root: str):
    if not os.path.isdir(root):
        return None
    try:
        return git.Repo(root).git.describe("--tag", "--abbrev=0")
    except git.exc.GitCommandError:
        return None


def flutter_checkout_matches(root: str, tag: str) -> bool:
    """True when the checkout at root already matches the requested tag.

    Stable tags (semver) compare via nearest-tag describe; branch names
    such as 'main' compare via branch/commit since describe would return
    the nearest stable tag instead.
    """
    if not tag or not os.path.isdir(root):
        return False
    try:
        repo = git.Repo(root)
    except (git.exc.GitCommandError, git.exc.InvalidGitRepositoryError):
        return False
    if re.fullmatch(r"\d+\.\d+\.\d+", tag):
        try:
            return repo.git.describe("--tag", "--abbrev=0") == tag
        except git.exc.GitCommandError:
            return False
    try:
        if repo.git.rev_parse("--abbrev-ref", "HEAD") == tag:
            return True
    except git.exc.GitCommandError:
        pass
    try:
        return repo.git.rev_parse("HEAD") == repo.git.rev_parse(tag)
    except git.exc.GitCommandError:
        return False


# TODO: see bin/internal/update_engine_version.sh
def engine_version(root: str):
    version_file = os.path.join(root, "bin/internal/engine.version")
    if os.path.isfile(version_file):
        with open(version_file) as f:
            return f.read()
    # bin/internal/engine.version is only checked in on stable/beta release
    # branches. On main the engine sources ship in-repo, so the engine
    # revision is the checkout HEAD.
    return git.Repo(root).git.rev_parse("HEAD").strip()


def recordm(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if os.environ.get("NO_RECORD"):
            return func(*args, **kwargs)
        if args and inspect.isclass(type(args[0])):
            class_name = args[0].__class__.__name__
            logged_args = args[1:]
        else:
            class_name = ""
            logged_args = args

        method = func.__name__
        if class_name:
            method = f"{class_name}.{method}"

        logged_args = [str(it) for it in logged_args]
        for k, v in kwargs.items():
            logged_args.append(f"{k}={v}")
        logged_args = ", ".join(logged_args)

        logger.debug(f"{method}({logged_args})")
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception(f"{method} failed")
            raise

    return wrapper


def record(cls):
    for name, method in vars(cls).items():
        if callable(method) and not name.startswith("__"):
            setattr(cls, name, recordm(method))
    return cls


if __name__ == "__main__":
    import fire

    fire.Fire()
