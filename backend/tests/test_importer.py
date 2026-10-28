import io
import zipfile

import pytest

from gostdoc_engine import importer
from gostdoc_engine.analyze import analyze
from gostdoc_engine.importer import InputError, load_docx, text_to_docx
from gostdoc_engine.model import Role
from tests.builders import build_docx


def to_bytes(doc):
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_load_ok():
    doc = load_docx(to_bytes(build_docx([("p", "Текст")])))
    assert doc.paragraphs[0].text == "Текст"


def test_too_big():
    with pytest.raises(InputError, match="Файл больше 20 МБ"):
        load_docx(b"0" * (importer.MAX_BYTES + 1))


def test_garbage():
    with pytest.raises(InputError, match="не похож на документ Word"):
        load_docx(b"garbage bytes")


def test_zip_not_docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.txt", "x")
    with pytest.raises(InputError, match="не похож на документ Word"):
        load_docx(buf.getvalue())


def test_encrypted():
    data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"E\0n\0c\0r\0y\0p\0t\0e\0d\0P\0a\0c\0k\0a\0g\0e\0"
    with pytest.raises(InputError, match="защищён паролем"):
        load_docx(data)


def test_ole_without_encryption():
    with pytest.raises(InputError, match="не похож на документ Word"):
        load_docx(b"\xd0\xcf\x11\xe0" + b"\0" * 50)


def test_text_to_docx():
    doc = text_to_docx("ВВЕДЕНИЕ\r\n\r\n\r\nТекст\tработы.\n1 Обзор\nЕщё текст.")
    m = analyze(doc)
    assert [p.role for p in m.paragraphs] == [
        Role.STRUCTURAL,
        Role.BODY,
        Role.HEADING_1,
        Role.BODY,
    ]
    assert [p.text for p in m.paragraphs] == [
        "ВВЕДЕНИЕ",
        "Текст работы.",
        "1 Обзор",
        "Ещё текст.",
    ]
    assert doc.paragraphs[0].style.name == "Heading 1"
    assert doc.paragraphs[2].style.name == "Heading 1"
    assert doc.paragraphs[1].style.name == "Normal"


def test_text_to_docx_levels_and_cr():
    doc = text_to_docx("1.1 Рынок\r1.1.1 Сегмент\r\r  текст  ")
    assert [p.style.name for p in doc.paragraphs] == ["Heading 2", "Heading 3", "Normal"]
    assert doc.paragraphs[2].text == "текст"


def test_text_empty():
    for t in ("", "  \n\t\r\n"):
        with pytest.raises(InputError, match="Текст пустой"):
            text_to_docx(t)
