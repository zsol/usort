# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import sys
from pathlib import Path
from typing import Iterable, Optional

from .config import Config
from .sorting import ImportSortingTransformer
from .types import Result
from .util import timed, try_parse, walk

__all__ = ["usort_string", "usort_stdin", "usort_path", "Config", "Result"]


def usort_string(data: str, config: Config, path: Optional[Path] = None) -> str:
    if path is None:
        path = Path("<data>")

    mod = try_parse(data=data.encode(), path=path)
    with timed(f"sorting {path}"):
        tr = ImportSortingTransformer(config, mod)
        new_mod = mod.visit(tr)
        return new_mod.code


def usort_stdin() -> bool:
    """
    Read file contents from stdin, format it, and write the resulting file to stdout

    In case of error during sorting, no output will be written to stdout, and the
    exception will be written to stderr instead.

    Returns True if formatting succeeded, otherwise False
    """
    if sys.stdin.isatty():
        print("Warning: stdin is a tty", file=sys.stderr)

    try:
        config = Config.find()
        data = sys.stdin.read()
        result = usort_string(data, config, Path("<stdin>"))
        sys.stdout.write(result)
        return True

    except Exception as e:
        sys.stderr.write(repr(e))
        return False


def usort_path(path: Path, *, write: bool = False) -> Iterable[Result]:
    """
    For a given path, format it, or any .py files in it, and yield Result objects
    """
    files: Iterable[Path]
    if path.is_dir():
        files = walk(path, "*.py")
    else:
        files = [path]

    for f in files:
        try:
            config = Config.find(f.parent)
            data = f.read_text()
            output = usort_string(data, config, f)
            if write:
                f.write_text(output)
            yield Result(f, data, output)

        except Exception as e:
            yield Result(f, data, "", e)
