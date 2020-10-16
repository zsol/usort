# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from contextlib import contextmanager
from fnmatch import fnmatch
from pathlib import Path
from time import monotonic
from typing import Callable, Generator, Iterable, List, Optional, Tuple

import libcst as cst

TIMINGS: List[Tuple[str, float]] = []


@contextmanager
def timed(msg: str) -> Generator[None, None, None]:
    """
    Records the monotonic duration of the contained context, with a given description.

    Timings are stored for later use/printing with `print_timings()`.
    """
    before = monotonic()
    yield
    after = monotonic()
    TIMINGS.append((msg, after - before))


def print_timings(fn: Callable[[str], None] = print) -> None:
    """
    Print all stored timing values in microseconds.
    """
    for msg, duration in TIMINGS:
        fn(f"{msg + ':':50} {int(duration*1000000):7} µs")


def walk(path: Path, glob: str) -> Iterable[Path]:
    with timed(f"walking {path}"):
        paths: List[Path] = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            root_path = Path(root)
            for f in files:
                if fnmatch(f, glob):
                    paths.append(root_path / f)
        return paths


def try_parse(path: Path, data: Optional[bytes] = None) -> cst.Module:
    """
    Attempts to parse the file with all syntax versions known by LibCST.

    If none parse, raises an exception that tells you that (what we know, not an
    error that might not be the most helpful).
    """
    if data is None:
        data = path.read_bytes()

    with timed(f"parsing {path}"):
        for version in cst.KNOWN_PYTHON_VERSION_STRINGS[::-1]:
            try:
                mod = cst.parse_module(
                    data, cst.PartialParserConfig(python_version=version)
                )
                return mod
            except cst.ParserSyntaxError:
                continue

        # Intentionally not raising an exception with a specific syntax error (if we
        # keep the last, meaning oldest python version, then it might complain about
        # typehints like https://github.com/psf/black/issues/1158)
        raise Exception(f"No version could parse {path}")


def with_dots(x: cst.CSTNode) -> str:
    """
    Helper to make it easier to use an Attribute or Name.
    """
    if isinstance(x, cst.Attribute):
        return ".".join([with_dots(x.value), with_dots(x.attr)])
    elif isinstance(x, cst.Name):
        return x.value
    else:
        raise TypeError(f"Can't with_dots on {type(x)}")


def top_level_name(x: str) -> str:
    """
    Returns the name that will be bound from a potentially-dotted import.

    This is used for two purposes -- checking the category of top-level names, and
    detecting name shadowing.

    Consider the two statements::

        import os.path
        import os.posixpath

    Both of these do the same thing to `locals()` -- bind the name `os`.  Neither
    shadows the other since it is the same name with the same target.
    """
    return x.split(".", 1)[0]


def stemjoin(stem: Optional[str], name: str) -> str:
    """
    Returns something like a qualname for an import.

    For an import statement like::

        from x import y as z

    You would typically call this with `stem="x", name="y"` to get a key that refers to
    the name that's being imported, not the name that's being locally bound.  Note that
    relative imports are not resolved (here, or elsewhere) and are not actually valid
    qualnames but can still be compared.

    Example::

        from . import foo.bar -> stemjoin(".", "foo.bar") -> ".foo.bar"
        from .foo import bar -> stemjoin(".foo", "bar") -> ".foo.bar"
    """

    if stem is None:
        return name
    elif stem.endswith("."):
        return stem + name
    else:
        return stem + "." + name
