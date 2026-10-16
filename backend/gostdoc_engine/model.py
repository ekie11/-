"""Модель документа: роли абзацев и обёртка над python-docx."""

from dataclasses import dataclass
from enum import StrEnum

import docx
from docx.text.paragraph import Paragraph


class Role(StrEnum):
    BODY = "BODY"
    HEADING_1 = "HEADING_1"
    HEADING_2 = "HEADING_2"
    HEADING_3 = "HEADING_3"
    STRUCTURAL = "STRUCTURAL"
    FIGURE_CAPTION = "FIGURE_CAPTION"
    TABLE_CAPTION = "TABLE_CAPTION"
    LIST_ITEM = "LIST_ITEM"
    TOC = "TOC"
    TITLE_PAGE = "TITLE_PAGE"
    EMPTY = "EMPTY"
    IN_TABLE = "IN_TABLE"


@dataclass
class DocParagraph:
    index: int
    role: Role
    text: str
    para: Paragraph


@dataclass
class DocModel:
    doc: "docx.document.Document"
    paragraphs: list[DocParagraph]

    def by_role(self, *roles: Role) -> list[DocParagraph]:
        return [p for p in self.paragraphs if p.role in roles]
