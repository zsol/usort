# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import libcst as cst

from .config import CAT_FIRST_PARTY, Category, Config
from .util import stemjoin, top_level_name


@dataclass(order=True)
class SortableImportItem:
    name: str
    # TODO comparable asname
    asname: Optional[str] = field(default=None, compare=False)

    directive_lines: Sequence[str] = ()
    comment_lines: Sequence[str] = ()
    inline_comments: Sequence[str] = ()


@dataclass(order=True)
class SortKey:
    category_index: int
    is_from_import: bool
    ndots: int


@dataclass
class ImportComments:
    before: Sequence[str]
    first_inline: Sequence[str]
    initial: Sequence[str]
    inline: Sequence[str]  # Only when no trailing comma
    final: Sequence[str]
    last_inline: Sequence[str]


@dataclass(order=True)
class SortableImport:
    sort_key: SortKey = field(init=False)
    # non-"from" imports have None
    stem: Optional[str]

    imports: Sequence[SortableImportItem]

    # Only needed for looking up category
    config: Config = field(repr=False, compare=False)

    @property
    def imported_names(self) -> Dict[str, str]:
        """
        Returns a dict of something like {localname: qualname} for determining whether
        names are being shadowed.
        """
        if self.stem is None:
            tmp: Dict[str, str] = {}
            for item in self.imports:
                if not item.asname:
                    top = top_level_name(item.name)
                    tmp[top] = top
                else:
                    tmp[item.asname or item.name] = item.name
            return tmp
        else:
            return {
                (item.asname or item.name): stemjoin(self.stem, item.name)
                for item in self.imports
            }

    def __post_init__(self) -> None:
        category: Category
        if self.stem is None:
            ndots = 0
            category = self.config.category(top_level_name(self.imports[0].name))
        elif not self.stem.startswith("."):
            ndots = 0
            category = self.config.category(top_level_name(self.stem))
        else:
            # replicate ... sorting before .. before ., but after absolute
            ndots = 100 - (len(self.stem) - len(self.stem.lstrip(".")))
            category = CAT_FIRST_PARTY

        self.sort_key = SortKey(
            # TODO this will raise on missing category
            category_index=self.config.categories.index(category),
            is_from_import=self.stem is not None,
            ndots=ndots,
        )


@dataclass(order=True)
class UneditableImport(SortableImport):
    """
    An import that we don't want to edit (yet) but should still sort relative to other
    imports.
    """

    node: cst.SimpleStatementLine = field(repr=False, compare=False)


@dataclass(order=True)
class EditableImport(SortableImport):
    """
    A fully-parsed import (see usort/translate.py) which can be re-flowed and combined.

    The base class stores `stem` and `imports` (probably with their comments).
    """

    comment_lines: Sequence[str] = ()
    directive_lines: Sequence[str] = ()

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
