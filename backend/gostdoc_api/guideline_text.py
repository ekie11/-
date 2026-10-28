"""Извлечение текста методички из DOCX/PDF."""

from __future__ import annotations

import io

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

MAX_CHARS = 150_000
MIN_PDF_CHARS = 200


class GuidelineError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _docx_text(data: bytes) -> str:
    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:
        raise GuidelineError("Не удалось прочитать DOCX-файл") from exc
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append(Paragraph(child, doc).text)
        elif tag == "tbl":
            for row in Table(child, doc).rows:
                seen: set[int] = set()
                cells = []
                for cell in row.cells:
                    if id(cell._tc) in seen:
                        continue
                    seen.add(id(cell._tc))
                    cells.append(cell.text.replace("\n", " "))
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
    except Exception as exc:
        raise GuidelineError("Не удалось прочитать PDF-файл") from exc
    if sum(len(p.strip()) for p in pages) < MIN_PDF_CHARS:
        raise GuidelineError("В PDF нет текста — похоже на скан")
    return "\n".join(f"[стр. {i}]\n{t}" for i, t in enumerate(pages, 1))


def extract_text(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".docx"):
        return _docx_text(data)
    if name.endswith(".pdf"):
        return _pdf_text(data)
    raise GuidelineError("Поддерживаются DOCX и PDF")


def check_text(text: str) -> str:
    if not text.strip():
        raise GuidelineError("Текст методички пуст")
    if len(text) > MAX_CHARS:
        raise GuidelineError(
            "Методичка слишком большая — до 150 000 символов (~60 страниц)", 413
        )
    return text
