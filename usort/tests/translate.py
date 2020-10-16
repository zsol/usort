# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest

import libcst as cst

from ..config import Config
from ..sorting import is_sortable_import
from ..translate import from_node, parse_alias_comments, parse_import_comments
from ..types import SortableImport


def si_from_str(s: str) -> SortableImport:
    stmt = cst.parse_statement(s)
    assert isinstance(stmt, cst.SimpleStatementLine)
    return from_node(stmt, Config())


class SortableImportTest(unittest.TestCase):
    def test_from_node_Import(self) -> None:
        imp = si_from_str("import a")
        self.assertEqual(None, imp.stem)
        # self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": "a"}, imp.imported_names)

        imp = si_from_str("import a, b")
        self.assertEqual(None, imp.stem)
        # self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": "a", "b": "b"}, imp.imported_names)

        imp = si_from_str("import a as b")
        self.assertEqual(None, imp.stem)
        # self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"b": "a"}, imp.imported_names)

        imp = si_from_str("import os.path")
        self.assertEqual(None, imp.stem)
        # "os.path", imp.stem)
        # self.assertEqual("os.path", imp.first_dotted_import)
        self.assertEqual({"os": "os"}, imp.imported_names)

        imp = si_from_str("import IPython.core")
        self.assertEqual(None, imp.stem)
        # self.assertEqual("ipython.core", imp.first_dotted_import)
        self.assertEqual({"IPython": "IPython"}, imp.imported_names)

    def test_from_node_ImportFrom(self) -> None:
        imp = si_from_str("from a import b")
        self.assertEqual("a", imp.stem)
        # self.assertEqual("b", imp.first_dotted_import)
        self.assertEqual({"b": "a.b"}, imp.imported_names)

        imp = si_from_str("from a import b as c")
        self.assertEqual("a", imp.stem)
        # self.assertEqual("b", imp.first_dotted_import)
        self.assertEqual({"c": "a.b"}, imp.imported_names)

    def test_from_node_ImportFrom_relative(self) -> None:
        imp = si_from_str("from .a import b")
        self.assertEqual(".a", imp.stem)
        self.assertEqual({"b": ".a.b"}, imp.imported_names)

        imp = si_from_str("from ...a import b")
        self.assertEqual("...a", imp.stem)
        # self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"b": "...a.b"}, imp.imported_names)

        imp = si_from_str("from . import a")
        self.assertEqual(".", imp.stem)
        # self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": ".a"}, imp.imported_names)

        imp = si_from_str("from .. import a")
        self.assertEqual("..", imp.stem)
        # self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": "..a"}, imp.imported_names)

        imp = si_from_str("from . import a as b")
        self.assertEqual(".", imp.stem)
        # self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"b": ".a"}, imp.imported_names)


class ParseAliasCommentsTest(unittest.TestCase):
    def test_parse_alias_comments(self) -> None:
        stmt = cst.parse_statement(
            """\
from a import (
    b, # comment
)
"""
        )
        alias = cst.ensure_type(
            cst.ensure_type(stmt, cst.SimpleStatementLine).body[0], cst.ImportFrom
        ).names[0]
        obj = parse_alias_comments(alias)
        self.assertEqual(["# comment"], obj.inline)
        self.assertEqual([], obj.following)

    def test_parse_alias_comments2(self) -> None:
        stmt = cst.parse_statement(
            """\
from a import (
    b # comment
    ,
)
"""
        )
        alias = cst.ensure_type(
            cst.ensure_type(stmt, cst.SimpleStatementLine).body[0], cst.ImportFrom
        ).names[0]
        obj = parse_alias_comments(alias)
        self.assertEqual(["# comment"], obj.inline)
        self.assertEqual([], obj.following)

    def test_parse_alias_comments3(self) -> None:
        stmt = cst.parse_statement(
            """\
from a import (
    b,
    # line after
    c,
)
"""
        )
        alias = cst.ensure_type(
            cst.ensure_type(stmt, cst.SimpleStatementLine).body[0], cst.ImportFrom
        ).names[0]
        obj = parse_alias_comments(alias)
        self.assertEqual([], obj.inline)
        self.assertEqual(["# line after"], obj.following)

    def test_parse_alias_comments4(self) -> None:
        stmt = cst.parse_statement(
            """\
from a import (
    b
)
"""
        )
        alias = cst.ensure_type(
            cst.ensure_type(stmt, cst.SimpleStatementLine).body[0], cst.ImportFrom
        ).names[0]
        obj = parse_alias_comments(alias)
        self.assertEqual([], obj.inline)
        self.assertEqual([], obj.following)


class ParseImportCommentsTest(unittest.TestCase):
    def test_import_comments0(self) -> None:
        stmt = cst.parse_statement(
            """\
# directive
import a # inline
"""
        )
        obj = parse_import_comments(cst.ensure_type(stmt, cst.SimpleStatementLine))
        self.assertEqual(("# directive",), obj.before)
        self.assertEqual(("# inline",), obj.first_inline)
        self.assertEqual((), obj.initial)
        self.assertEqual((), obj.inline)
        self.assertEqual((), obj.final)
        self.assertEqual((), obj.last_inline)

    def test_from_import_no_comments(self) -> None:
        stmt = cst.parse_statement(
            """\
from a import b
"""
        )
        obj = parse_import_comments(cst.ensure_type(stmt, cst.SimpleStatementLine))
        self.assertEqual((), obj.first_inline)
        self.assertEqual((), obj.initial)
        self.assertEqual((), obj.inline)
        self.assertEqual((), obj.final)
        self.assertEqual((), obj.last_inline)

    def test_from_import_comments0(self) -> None:
        stmt = cst.parse_statement(
            """\
# directive
from a import b # inline
"""
        )
        obj = parse_import_comments(cst.ensure_type(stmt, cst.SimpleStatementLine))
        self.assertEqual(("# directive",), obj.before)
        self.assertEqual(("# inline",), obj.first_inline)
        self.assertEqual((), obj.initial)
        self.assertEqual((), obj.inline)
        self.assertEqual((), obj.final)
        self.assertEqual((), obj.last_inline)

    def test_from_import_comments1(self) -> None:
        stmt = cst.parse_statement(
            """\
# pre
from a import ( # first
    # directive
    b # inline
    # after
) # last
# post
"""
        )
        obj = parse_import_comments(cst.ensure_type(stmt, cst.SimpleStatementLine))
        self.assertEqual(("# pre",), obj.before)
        self.assertEqual(("# first",), obj.first_inline)
        self.assertEqual(("# directive",), obj.initial)
        self.assertEqual(("# inline",), obj.inline)
        self.assertEqual(("# after",), obj.final)
        # self.assertEqual(["# last"], obj.last_inline)


'''
    def test_node_comments(self) -> None:
        imp = si_from_str(
            """\
# x1
import a  # x2
"""
        )
        self.assertEqual(["# x1"], imp.comment_lines)
        self.assertEqual(["# x2"], imp.inline_last_comments)

    def test_from_node_comments(self) -> None:
        imp = si_from_str(
            """\
# x1
from a import ( # x2  # x2b
    # x3
    b # x4  # x4b
    , # x5
    # x6
) # x7
"""
        )
        self.assertEqual(["# x1"], imp.comment_lines)
        # TODO
        # self.assertEqual(["# x6"], imp.extra_inside_comment)
        self.assertEqual(["# x2", "# x2b"], imp.inline_first_comments)
        self.assertEqual(["# x7"], imp.inline_last_comments)

        self.assertEqual(["# x3"], imp.imported_items[0].directive_lines)
        self.assertEqual(
            ["# x4", "# x4b", "# x5"], imp.imported_items[0].inline_comments
        )
'''


class IsSortableTest(unittest.TestCase):
    def test_is_sortable(self) -> None:
        self.assertTrue(is_sortable_import(cst.parse_statement("import a")))
        self.assertTrue(is_sortable_import(cst.parse_statement("from a import b")))
        self.assertFalse(
            is_sortable_import(cst.parse_statement("import a  # isort: skip"))
        )
