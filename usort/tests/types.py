# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest

from ..config import Config
from ..types import SortableImport, SortableImportItem


class ImportedNamesTest(unittest.TestCase):
    def test_import(self) -> None:
        # import a
        imp = SortableImport(
            stem=None, imports=(SortableImportItem(name="a"),), config=Config()
        )
        self.assertEqual(
            {"a": "a"}, imp.imported_names,
        )

    def test_import_as(self) -> None:
        # import a as b
        imp = SortableImport(
            stem=None,
            imports=(SortableImportItem(name="a", asname="b"),),
            config=Config(),
        )
        self.assertEqual(
            {"b": "a"}, imp.imported_names,
        )

    def test_import_dotted(self) -> None:
        # import os.path
        imp = SortableImport(
            stem=None, imports=(SortableImportItem(name="os.path"),), config=Config(),
        )
        self.assertEqual(
            {"os": "os"}, imp.imported_names,
        )

    def test_import_dotted_as(self) -> None:
        # import os.path as osp
        imp = SortableImport(
            stem=None,
            imports=(SortableImportItem(name="os.path", asname="osp"),),
            config=Config(),
        )
        self.assertEqual(
            {"osp": "os.path"}, imp.imported_names,
        )

    def test_from_import(self) -> None:
        # from a import b
        imp = SortableImport(
            stem="a", imports=(SortableImportItem(name="b"),), config=Config(),
        )
        self.assertEqual(
            {"b": "a.b"}, imp.imported_names,
        )

    def test_from_import_as(self) -> None:
        # from a import b as c
        imp = SortableImport(
            stem="a",
            imports=(SortableImportItem(name="b", asname="c"),),
            config=Config(),
        )
        self.assertEqual(
            {"c": "a.b"}, imp.imported_names,
        )

    def test_relative(self) -> None:
        # from .a import b
        imp = SortableImport(
            stem=".a", imports=(SortableImportItem(name="b"),), config=Config(),
        )
        self.assertEqual(
            {"b": ".a.b"}, imp.imported_names,
        )

    def test_relative_many(self) -> None:
        # from ...a import b
        imp = SortableImport(
            stem="...a", imports=(SortableImportItem(name="b"),), config=Config(),
        )
        self.assertEqual(
            {"b": "...a.b"}, imp.imported_names,
        )
