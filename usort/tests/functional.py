# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from textwrap import dedent
from typing import Optional

from ..api import usort_string
from ..config import Config
from ..translate import import_from_node
from ..util import parse_import

DEFAULT_CONFIG = Config()


class BasicOrderingTest(unittest.TestCase):
    maxDiff = None

    def test_order(self) -> None:
        items_in_order = [
            "from __future__ import division",
            "import os",
            "from os import path",
            "import tp",
            "from tp import x",
            "from .. import c",
            "from . import a",
            "from . import b",
            "from .a import z",
        ]

        nodes = [
            import_from_node(parse_import(x), config=DEFAULT_CONFIG)
            for x in items_in_order
        ]
        self.assertSequenceEqual(nodes, sorted(nodes))


class UsortStringFunctionalTest(unittest.TestCase):
    def assertUsortResult(
        self, before: str, after: str, config: Optional[Config] = None
    ) -> None:
        before = dedent(before)
        after = dedent(after)
        config = config or DEFAULT_CONFIG
        result = usort_string(before, config)
        if result != after:
            self.fail(
                "µsort result did not match expected value:\n\n"
                f"Before:\n-------\n{before}\nExpected:\n---------\n{after}\nResult:\n-------\n{result}"
            )

    def test_sort_ordering(self) -> None:
        # This only tests ordering, not any of the comment or whitespace
        # modifications.
        self.assertUsortResult(
            """
                import a
                import a.b
                from a.b import foo2
                from a import foo
                import b
            """,
            """
                import a
                import a.b
                import b
                from a import foo
                from a.b import foo2
            """,
        )

    def test_sort_blocks(self) -> None:
        # This only tests that there are two blocks and we only reorder within a
        # block
        self.assertUsortResult(
            """
                import d
                import c
                print("hi")
                import b
                import a
            """,
            """
                import c
                import d
                print("hi")
                import a
                import b
            """,
        )

    # Disabled until wrapping is supported
    #     def test_sort_wrap_moves_comments(self):
    #         # Test that end-of-line directive comments get moved to the first line
    #         # when wrapping is going to happen.
    #         self.assertEqual(
    #             """\
    # from a (  # pylint: disable=E1
    #     import foo,
    # )
    # """,
    #             usort_string(
    #                 """\
    # from a import foo  # pylint: disable=E1
    # """,
    #                 line_limit=10,
    #             ),
    #         )

    def test_star_imports(self) -> None:
        # Test that we create a second block with the star import
        self.assertUsortResult(
            """
                import d
                import c
                from x import *
                import b
                import a
            """,
            """
                import c
                import d
                from x import *
                import a
                import b
            """,
        )

    def test_shadowed_import(self) -> None:
        # Test that a new block is started when there's a duplicate name
        self.assertUsortResult(
            """
                import b as b
                import a as b
            """,
            """
                import b as b
                import a as b
            """,
        )

    def test_shadowed_import_ok(self) -> None:
        self.assertUsortResult(
            """
                import a.d
                import a.c
                import a.b
            """,
            """
                import a.b
                import a.c
                import a.d
            """,
        )

    def test_shadowed_relative_import_ok(self) -> None:
        self.assertUsortResult(
            """
                from os import path as path
                from os import path
                import os.path as path
            """,
            """
                import os.path as path
                from os import path as path
                from os import path
            """,
        )

    def test_dot_handling(self) -> None:
        # Test that 'from .. import b' comes before 'from ..a import foo'
        self.assertUsortResult(
            """
                from ..a import foo
                from .. import b
                from . import d
                from fp import z
                import fp
                from .c import e
            """,
            """
                import fp
                from fp import z

                from .. import b
                from ..a import foo
                from . import d
                from .c import e
            """,
        )

    def test_customized_sections(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pyproject.toml").write_text(
                """\
[tool.usort]
categories = ["future", "standard_library", "numpy", "third_party", "first_party"]
[tool.usort.known]
numpy = ["numpy", "pandas"]
"""
            )
            sample = Path(d) / "sample.py"
            conf = Config.find(sample)
            self.assertUsortResult(
                """
                    import os
                    from . import foo
                    import numpy as np
                    import aaa
                """,
                """
                    import os

                    import numpy as np

                    import aaa

                    from . import foo
                """,
                conf,
            )

    def test_non_module_imports(self) -> None:
        self.assertUsortResult(
            """
                if True:
                    import b
                    import a

                def func():
                    import d
                    import c
                    if True:
                        import f
                        import e
                        pass
                        import a
            """,
            """
                if True:
                    import a
                    import b

                def func():
                    import c
                    import d
                    if True:
                        import e
                        import f
                        pass
                        import a
            """,
        )

    def test_whitespace_between_sections(self) -> None:
        self.assertUsortResult(
            """
                from __future__ import unicode_literals
                from __future__ import division
                import sys



                import third_party
                #comment
                from . import first_party
            """,
            """
                from __future__ import division
                from __future__ import unicode_literals

                import sys

                import third_party

                #comment
                from . import first_party
            """,
        )

    def test_case_insensitive_sorting(self) -> None:
        content = """
            import calendar
            import cProfile
            import dataclasses

            from fissix.main import diff_texts
            from IPython import start_ipython
            from libcst import Module
        """
        self.assertUsortResult(content, content)

    def test_side_effect_modules(self) -> None:
        config = replace(
            DEFAULT_CONFIG,
            side_effect_modules=["tracemalloc", "fizzbuzz", "foo.bar.baz"],
        )
        content = """
            from zipfile import ZipFile
            from tracemalloc import start
            from collections import defaultdict

            import fizzbuzz
            import attr
            import solar
            import foo.bar.baz
            from foo import bar
            from star import sun
            from foo.bar import baz
            from attr import evolve
        """
        self.assertUsortResult(content, content, config)

    def test_match_black_blank_line_before_comment(self) -> None:
        content = """
            import a
            import b

            # comment
            import c
        """
        self.assertUsortResult(content, content)

    def test_multi_line_maintain(self) -> None:
        self.assertUsortResult(
            """
                from fuzz import buzz
                # one
                from foo import (  # two
                    # three
                    bar,  # four
                    # five
                    baz # six
                    , # seven
                    # eight
                )  # nine
                # ten
            """,
            """
                # one
                from foo import (  # two
                    # three
                    bar,  # four
                    # five
                    baz,  # six  # seven
                    # eight
                )  # nine
                from fuzz import buzz
                # ten
            """,
        )

    def test_multi_line_maintain_inner(self) -> None:
        self.assertUsortResult(
            """
                def foo():
                    from fuzz import buzz
                    # one
                    from foo import (  # two
                        # three
                        bar,  # four
                        # five
                        baz # six
                        , # seven
                        # eight
                    )  # nine
                    # ten
            """,
            """
                def foo():
                    # one
                    from foo import (  # two
                        # three
                        bar,  # four
                        # five
                        baz,  # six  # seven
                        # eight
                    )  # nine
                    from fuzz import buzz
                    # ten
            """,
        )

    def test_multi_line_collapse(self) -> None:
        self.assertUsortResult(
            """
                from fuzz import buzz
                # 1
                from foo import (  # 2
                    # 3
                    bar,  # 4
                    # 5
                    baz # 6
                    , # 7
                )  # 8
                # 9
            """,
            """
                # 1
                from foo import bar, baz  # 2  # 3  # 4  # 5  # 6  # 7  # 8
                from fuzz import buzz
                # 9
            """,
        )

    def test_multi_line_collapse_inner(self) -> None:
        self.assertUsortResult(
            """
                def foo():
                    from fuzz import buzz
                    # 1
                    from foo import (  # 2
                        # 3
                        bar,  # 4
                        # 5
                        baz # 6
                        , # 7
                    )  # 8
                    # 9
            """,
            """
                def foo():
                    # 1
                    from foo import bar, baz  # 2  # 3  # 4  # 5  # 6  # 7  # 8
                    from fuzz import buzz
                    # 9
            """,
        )

    def test_maintain_tabs(self) -> None:
        self.assertUsortResult(
            """
                import foo

                def a():
                \timport bar
                \t
                \tdef b():
                \t\timport baz
            """,
            """
                import foo

                def a():
                \timport bar
                \t
                \tdef b():
                \t\timport baz
            """,
        )

    def test_multi_line_expand_top_level(self) -> None:
        self.assertUsortResult(
            """
                from really_absurdly_long_python_module_name.insanely_long_submodule_name import SomeReallyObnoxiousCamelCaseClass
            """,
            """
                from really_absurdly_long_python_module_name.insanely_long_submodule_name import (
                    SomeReallyObnoxiousCamelCaseClass,
                )
            """,
        )

    def test_multi_line_expand_function(self) -> None:
        self.assertUsortResult(
            """
                def foo():
                    from really_absurdly_long_python_module_name.insanely_long_submodule_name import SomeReallyObnoxiousCamelCaseClass
            """,
            """
                def foo():
                    from really_absurdly_long_python_module_name.insanely_long_submodule_name import (
                        SomeReallyObnoxiousCamelCaseClass,
                    )
            """,
        )

    def test_multi_line_expand_inner_function(self) -> None:
        self.assertUsortResult(
            """
                def foo():
                    import b
                    import a

                    def bar():
                        from really_absurdly_long_python_module_name.insanely_long_submodule_name import SomeReallyObnoxiousCamelCaseClass
            """,
            """
                def foo():
                    import a
                    import b

                    def bar():
                        from really_absurdly_long_python_module_name.insanely_long_submodule_name import (
                            SomeReallyObnoxiousCamelCaseClass,
                        )
            """,
        )


if __name__ == "__main__":
    unittest.main()
