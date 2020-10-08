# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest

import libcst as cst

from ..config import Config
from ..sorting import is_sortable_import
from ..translate import from_node
from ..types import SortableImport


def si_from_str(s: str) -> SortableImport:
    stmt = cst.parse_statement(s)
    assert isinstance(stmt, cst.SimpleStatementLine)
    return from_node(stmt, Config())


class SortableImportTest(unittest.TestCase):
    def test_from_node_Import(self) -> None:
        imp = si_from_str("import a")
        self.assertEqual("a", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": "a"}, imp.imported_names)

        imp = si_from_str("import a, b")
        self.assertEqual("a", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": "a", "b": "b"}, imp.imported_names)

        imp = si_from_str("import a as b")
        self.assertEqual("a", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"b": "a"}, imp.imported_names)

        imp = si_from_str("import os.path")
        self.assertEqual("os.path", imp.first_module)
        self.assertEqual("os.path", imp.first_dotted_import)
        self.assertEqual({"os": "os"}, imp.imported_names)

        imp = si_from_str("import IPython.core")
        self.assertEqual("ipython.core", imp.first_module)
        self.assertEqual("ipython.core", imp.first_dotted_import)
        self.assertEqual({"IPython": "IPython"}, imp.imported_names)

    def test_from_node_ImportFrom(self) -> None:
        imp = si_from_str("from a import b")
        self.assertEqual("a", imp.first_module)
        self.assertEqual("b", imp.first_dotted_import)
        self.assertEqual({"b": "a.b"}, imp.imported_names)

        imp = si_from_str("from a import b as c")
        self.assertEqual("a", imp.first_module)
        self.assertEqual("b", imp.first_dotted_import)
        self.assertEqual({"c": "a.b"}, imp.imported_names)

    def test_from_node_ImportFrom_relative(self) -> None:
        imp = si_from_str("from .a import b")
        self.assertEqual(".a", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"b": ".a.b"}, imp.imported_names)

        imp = si_from_str("from ...a import b")
        self.assertEqual("...a", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"b": "...a.b"}, imp.imported_names)

        imp = si_from_str("from . import a")
        self.assertEqual(".", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": ".a"}, imp.imported_names)

        imp = si_from_str("from .. import a")
        self.assertEqual("..", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"a": "..a"}, imp.imported_names)

        imp = si_from_str("from . import a as b")
        self.assertEqual(".", imp.first_module)
        self.assertEqual("a", imp.first_dotted_import)
        self.assertEqual({"b": ".a"}, imp.imported_names)


class IsSortableTest(unittest.TestCase):
    def test_is_sortable(self) -> None:
        self.assertTrue(is_sortable_import(cst.parse_statement("import a")))
        self.assertTrue(is_sortable_import(cst.parse_statement("from a import b")))
        self.assertFalse(
            is_sortable_import(cst.parse_statement("import a  # isort: skip"))
        )
