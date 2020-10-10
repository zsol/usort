# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import libcst as cst

from .config import Config


@dataclass(order=True)
class SortableImportItem:
    name: str
    asname: Optional[str] = None

    directive_lines: Sequence[str] = ()
    comment_lines: Sequence[str] = ()
    inline_comments: Sequence[str] = ()


@dataclass(order=True)
class SortKey:
    category_index: int
    is_from_import: bool
    ndots: int


@dataclass(order=True)
class SortableImport:
    node: cst.SimpleStatementLine = field(repr=False, compare=False)
    sort_key: SortKey = field(init=False)

    # For constructing the sort key...
    first_module: str
    first_dotted_import: str

    config: Config = field(repr=False, compare=False)

    directive_lines: Sequence[str] = ()
    comment_lines: Sequence[str] = ()

    # comment_lines
    # directive_lines
    # (once there's a directive_line, everything is a directive)
    # from x import ( # inline_first_comment
    #   # pre_comment for a
    #   a, # inline comment for a
    #
    #   # extra_inside_comment
    # ) # inline_last_comment
    #
    inline_first_comments: Sequence[str] = ()
    extra_inside_comment: Sequence[str] = ()
    inline_last_comments: Sequence[str] = ()

    # This is only used for detecting unsafe ordering, and is not used for
    # breaking ties.  e.g. `import a as b; import b.c` shadows `b`, but `import
    # os` and `import os.path` do not shadow becuase it's the same `os`
    imported_names: Dict[str, str] = field(default_factory=dict, compare=False)

    imported_items: Sequence[SortableImportItem] = ()

    def __post_init__(self) -> None:
        if not self.first_module.startswith("."):
            ndots = 0
        else:
            # replicate ... sorting before .. before ., but after absolute
            ndots = 100 - (len(self.first_module) - len(self.first_module.lstrip(".")))
        self.sort_key = SortKey(
            # TODO this will raise on missing category
            category_index=self.config.categories.index(
                self.config.category(self.first_module)
            ),
            is_from_import=isinstance(self.node.body[0], cst.ImportFrom),
            ndots=ndots,
        )


@dataclass
class SortableBlock:
    start_idx: int
    end_idx: Optional[int] = None  # half-open interval

    stmts: List[SortableImport] = field(default_factory=list)
    imported_names: Dict[str, str] = field(default_factory=dict)


@dataclass
class Result:
    path: Path
    content: str
    output: str
    error: Optional[Exception] = None
