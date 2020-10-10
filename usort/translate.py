import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

import libcst as cst

from .config import Config
from .types import SortableImport, SortableImportItem
from .util import with_dots

INLINE_COMMENT_RE = re.compile(r"#+[^#]*")


def from_node(node: cst.SimpleStatementLine, config: Config) -> SortableImport:
    # TODO: This duplicates (differently) what's in the LibCST import
    # metadata visitor.  This is also a bit hard to read.
    first_module: Optional[str] = None
    first_dotted_import: Optional[str] = None
    names: Dict[str, str] = {}
    items: List[SortableImportItem] = []
    sort_key: Optional[str] = None
    first_line_inline: List[str] = []
    last_line_inline: List[str] = []

    # There are 4 basic types of import
    # Additionally some forms z can have leading dots for relative
    # imports, and there can be multiple on the right-hand side.
    #
    if isinstance(node.body[0], cst.Import):
        # import z
        # import z as y
        for name in node.body[0].names:
            if name.asname:
                names[with_dots(name.asname.name).split(".")[0]] = with_dots(name.name)
            else:
                tmp = with_dots(name.name).split(".")[0]
                names[tmp] = tmp
            items.append(item_from_node(name))

            if first_module is None:
                first_module = with_dots(name.name)
                first_dotted_import = first_module

    elif isinstance(node.body[0], cst.ImportFrom):
        # from z import x
        # from z import x as y

        # This is treated as a barrier and should never get this far.
        assert not isinstance(node.body[0].names, cst.ImportStar)

        if node.body[0].module is None:
            # from . import foo [as bar]
            # (won't have dots but with_dots makes the typing easier)
            sort_key = with_dots(node.body[0].names[0].name)
            name_key = sort_key
        else:
            # from x import foo [as bar]
            sort_key = with_dots(node.body[0].module)
            name_key = sort_key + "."

        if node.body[0].relative:
            first_dotted_import = sort_key
            sort_key = "." * len(node.body[0].relative)
            if node.body[0].module is not None:
                sort_key += first_dotted_import
            name_key = sort_key
            if node.body[0].module is not None:
                name_key += "."

        if first_module is None:
            first_module = sort_key
            if first_dotted_import is None:
                for alias in node.body[0].names:
                    first_dotted_import = with_dots(alias.name)
                    break

        accumulated_directives: List[str] = []
        if (
            node.body[0].lpar
            and node.body[0].lpar.whitespace_after
            and node.body[0].lpar.whitespace_after.empty_lines
        ):
            for line in node.body[0].lpar.whitespace_after.empty_lines:
                if line.comment:
                    accumulated_directives.append(line.comment.value)

        # TODO use match
        if (
            node.body[0].lpar
            and node.body[0].lpar.whitespace_after
            and node.body[0].lpar.whitespace_after.first_line
            and node.body[0].lpar.whitespace_after.first_line.comment
        ):
            for x in INLINE_COMMENT_RE.findall(
                node.body[0].lpar.whitespace_after.first_line.comment.value
            ):
                first_line_inline.append(x.rstrip())

        for alias in node.body[0].names:
            if alias.asname:
                assert isinstance(alias.asname.name, cst.Name)
                names[alias.asname.name.value] = name_key + with_dots(alias.name)
            else:
                assert isinstance(alias.name, cst.Name)
                names[alias.name.value] = name_key + alias.name.value
            items.append(item_from_node(alias, accumulated_directives))
            accumulated_directives = []

    else:
        raise TypeError

    comment_lines: List[str] = []
    directive_lines: List[str] = []
    in_directive = False
    for line in node.leading_lines:
        # TODO prefix match?
        if line.comment and any(
            ind in line.comment.value for ind in config.directive_comments
        ):
            in_directive = True
        if not in_directive:
            comment_lines.append(line.comment and line.comment.value or "")
        else:
            directive_lines.append(line.comment and line.comment.value or "")

    # TODO detect wrapped statements
    tmp = node.trailing_whitespace.comment
    if tmp is not None:
        # TODO assert last match's end is actual end
        for inline_comment in INLINE_COMMENT_RE.findall(tmp.value):
            # TODO which should we default to?
            if any(ind in inline_comment for ind in config.first_line_inline_comments):
                first_line_inline.append(inline_comment.rstrip())
            else:
                last_line_inline.append(inline_comment.rstrip())

    assert first_module is not None
    assert first_dotted_import is not None
    return SortableImport(
        node=node,
        first_module=first_module.lower(),
        first_dotted_import=first_dotted_import.lower(),
        imported_names=names,
        config=config,
        directive_lines=directive_lines,
        comment_lines=comment_lines,
        inline_first_comments=first_line_inline,
        inline_last_comments=last_line_inline,
        imported_items=items,
    )


def item_from_node(
    node: cst.ImportAlias, directive_comments: Sequence[str] = ()
) -> SortableImportItem:
    inline_comments: List[str] = []
    if (
        isinstance(node.comma, cst.Comma)
        and isinstance(node.comma.whitespace_after, cst.ParenthesizedWhitespace)
        and node.comma.whitespace_after.first_line.comment
    ):
        for x in INLINE_COMMENT_RE.findall(
            node.comma.whitespace_after.first_line.comment.value
        ):
            inline_comments.append(x.rstrip())

    if node.asname:
        sii = SortableImportItem(
            name=with_dots(node.name),
            asname=with_dots(node.asname.name),
            directive_lines=directive_comments,
            inline_comments=inline_comments,
        )
    else:
        sii = SortableImportItem(
            name=with_dots(node.name),
            directive_lines=directive_comments,
            inline_comments=inline_comments,
        )
    return sii


@dataclass
class ImportComments:
    before: Sequence[str]
    first_inline: Sequence[str]
    initial: Sequence[str]
    inline: Sequence[str]  # Only when no trailing comma
    final: Sequence[str]
    last_inline: Sequence[str]


def parse_import_comments(node: Union[cst.Import, cst.ImportFrom]) -> ImportComments:
    before: List[str] = []
    first_inline: List[str] = []
    initial: List[str] = []
    inline: List[str] = []
    final: List[str] = []
    last_inline: List[str] = []

    if isinstance(node, cst.ImportFrom):
        if node.lpar:
            # assert isinstance(node.lpar.whitespace_after,
            # cst.ParenthesizedWhitespace)
            first_inline.extend(
                split_inline_comments(
                    node.lpar.whitespace_after.first_line.comment.value
                )
            )
            for line in node.lpar.whitespace_after.empty_lines:
                initial.append(line.comment.value)
            if isinstance(node.rpar.whitespace_before, cst.ParenthesizedWhitespace,):
                for line in node.rpar.whitespace_before.empty_lines:
                    final.append(line.comment.value)
                if node.rpar.whitespace_before.first_line.comment:
                    inline.extend(
                        split_inline_comments(
                            node.rpar.whitespace_before.first_line.comment.value
                        )
                    )
        # print(repr(node))

    return ImportComments(before, first_inline, initial, inline, final, last_inline)


@dataclass
class ImportItemComments:
    inline: Sequence[str]
    following: Sequence[str]


def parse_alias_comments(alias: cst.ImportAlias) -> ImportItemComments:
    a: List[str] = []
    b: List[str] = []

    if isinstance(alias.comma, cst.Comma):
        # Can also just be a SimpleWhitespace which doesn't have comment.
        if (
            isinstance(alias.comma.whitespace_before, cst.ParenthesizedWhitespace)
            and alias.comma.whitespace_before.first_line.comment
        ):
            # from a import (
            #   b  # THIS PART
            #   ,
            # )
            a.extend(
                split_inline_comments(
                    alias.comma.whitespace_before.first_line.comment.value
                )
            )

        if alias.comma.whitespace_after.first_line.comment:
            # from a import (
            #   b,  # THIS PART
            # )
            a.extend(
                split_inline_comments(
                    alias.comma.whitespace_after.first_line.comment.value
                )
            )

        # from a import (
        #    b,
        #    # THIS PART
        #    c, # (but only if it's not the last alias; that goes in the ImportFrom)
        # )
        for line in alias.comma.whitespace_after.empty_lines:
            b.append(line.comment.value)

    return ImportItemComments(a, b)


def split_inline_comments(text: str) -> Sequence[str]:
    return [t.rstrip() for t in INLINE_COMMENT_RE.findall(text)]


def to_node(si: SortableImport) -> cst.CSTNode:
    # TODO this needs to know config width
    temp_width = 88

    node = to_node_single_line(si)
    if check_width(node) > temp_width:
        node = to_node_multi_line(si)
    return node


def check_width(node: cst.CSTNode):
    tmp = node.with_changes(leading_lines=())
    return len(tmp.code)


def to_node_single_line(si: SortableImport) -> cst.CSTNode:
    # TODO eventually, don't store the whole node, but a flag.
    # Should also split multiple imports first.
    if isinstance(si.node.body, cst.Import):
        for it in si.imported_items:
            obj = cst.ImportAlias(name=attr_or_name(it.name))
            if it.asname:
                obj = obj.with_changes(asname=cst.AsName(name=cst.Name(it.asname)))

        line = cst.SimpleStatementLine(body=cst.Import())


def attr_or_name(x: str) -> Union[cst.Name, cst.Attribute]:
    if "." not in x:
        return cst.Name(x)
    tmp, rest = x.split(".", 1)

    while True:
        if "." not in rest:
            return cst.Attribute(value=tmp, attr=cst.Name(rest))
        else:
            a, rest = rest.split(".", 1)
            tmp = cst.Attribute(value=tmp, attr=cst.Name(a))


def to_node_multi_line(si: SortableImport) -> cst.CSTNode:
    pass
