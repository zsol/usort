# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Dict, List, Optional, Sequence, Tuple

import libcst as cst

# Compat, but also circular impoty
# from .api import usort_stdin, usort_string, usort_path
from .config import Config
from .translate import from_node, to_node
from .types import SortableBlock, SortableImport


def name_overlap(a: Dict[str, str], b: Dict[str, str]) -> bool:
    for k, v in b.items():
        if k in a and a[k] != v:
            return True
    return False


def sortable_blocks(
    body: Sequence[cst.BaseStatement], config: Config
) -> List[SortableBlock]:
    # Finds blocks of imports separated by barriers (non-import statements, or
    # dangerous imports).  We will only sort within a block, and only when there
    # are no duplicate names.

    ret: List[SortableBlock] = []
    cur: Optional[SortableBlock] = None
    for i, stmt in enumerate(body):
        # print(stmt)
        # TODO support known_side_effect_modules or so
        if is_sortable_import(stmt):
            assert isinstance(stmt, cst.SimpleStatementLine)
            imp = from_node(stmt, config)
            if cur is None:
                cur = SortableBlock(i, i + 1)
                ret.append(cur)

            if name_overlap(cur.imported_names, imp.imported_names):
                # This overwrites an earlier name
                cur = SortableBlock(i, i + 1)
                ret.append(cur)

            cur.end_idx = i + 1
            cur.stmts.append(imp)
            cur.imported_names.update(imp.imported_names)
        else:
            if cur:
                cur = None
    return ret


def is_sortable_import(stmt: cst.CSTNode) -> bool:
    if isinstance(stmt, cst.SimpleStatementLine):
        com = stmt.trailing_whitespace.comment
        if com:
            com_str = com.value.replace(" ", "")
            if com_str.startswith("#usort:skip") or com_str.startswith("#isort:skip"):
                return False

        # N.b. `body` is a list, because the SimpleStatementLine might have
        # semicolons.  We only look at the first, which is probably the most
        # dangerous thing in here.
        #
        # If black is run, it will put the semicolon pieces on different lines,
        # but we don't want to do that until we reflow and handle directives
        # like noqa.  TODO do that before calling is_sortable_import, and assert
        # that it's not a compound statement line.
        if isinstance(stmt.body[0], cst.ImportFrom):
            # `from x import *` is a barrier
            if isinstance(stmt.body[0].names, cst.ImportStar):
                return False
            return True
        elif isinstance(stmt.body[0], cst.Import):
            return True
        else:
            return False
    else:
        return False


def partition_leading_lines(
    lines: Sequence[str],
) -> Tuple[Sequence[str], Sequence[str]]:
    """
    Returns a tuple of the initial blank lines, and the comment lines.
    """
    for j in range(len(lines)):
        if lines[j].startswith("#"):
            break
    else:
        j = len(lines)

    return lines[:j], lines[j:]


def fixup_whitespace(
    initial_blank: Sequence[str], imports: List[SortableImport]
) -> List[SortableImport]:
    cur_category = None
    # TODO if they've already been reshuffled, there may have been a blank
    # (separator) line between a non-block and the first import, that's now in
    # the middle.
    for i in imports:
        if cur_category is None:
            blanks = initial_blank
        elif i.sort_key.category_index != cur_category:
            blanks = ("",)
        else:
            blanks = ()

        old_blanks, old_comments = partition_leading_lines(i.comment_lines)

        i.comment_lines = (*blanks, *old_comments)

        cur_category = i.sort_key.category_index
    return imports


class ImportSortingTransformer(cst.CSTTransformer):
    def __init__(self, config: Config, module: cst.Module) -> None:
        self.config = config

        # This might seem silly, but we need it for code_for_node on leaving
        # IndentedBlock too
        self.module = module

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        blocks = sortable_blocks(updated_node.body, config=self.config)
        body: List[cst.CSTNode] = list(updated_node.body)

        for b in blocks:
            initial_blank, initial_comment = partition_leading_lines(
                b.stmts[0].comment_lines
            )
            b.stmts[0].comment_lines = initial_comment
            sorted_stmts = fixup_whitespace(initial_blank, sorted(b.stmts))
            body[b.start_idx : b.end_idx] = [
                to_node(s, self.module) for s in sorted_stmts
            ]
        return updated_node.with_changes(body=body)

    # Close enough.
    leave_IndentedBlock = leave_Module
