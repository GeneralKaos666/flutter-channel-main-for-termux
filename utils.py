import inspect
import os
import re
from functools import wraps

import git
from loguru import logger

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
    root = os.path.join(root, "bin/internal/engine.version")

    with open(root) as f:
        return f.read()


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
