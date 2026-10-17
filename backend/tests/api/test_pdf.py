import os
import shutil
import stat
import time
from pathlib import Path

import pytest

from gostdoc_api.pdf import PdfError, render_pdf
from tests.builders import build_docx, save

MSG = "Не удалось построить PDF-предпросмотр"

# Фиктивный soffice: пишет "%PDF-1.4" в <outdir>/<stem>.pdf, где входной файл — последний аргумент.
FAKE_OK = """#!/bin/sh
prev=""
outdir=""
last=""
for arg in "$@"; do
  if [ "$prev" = "--outdir" ]; then outdir="$arg"; fi
  prev="$arg"
  last="$arg"
done
stem=$(basename "$last" .docx)
printf '%s' '%PDF-1.4' > "$outdir/$stem.pdf"
"""

FAKE_SLEEP = """#!/bin/sh
exec sleep 5
"""

FAKE_FAIL = """#!/bin/sh
echo "boom" >&2
exit 3
"""

FAKE_NO_OUTPUT = """#!/bin/sh
exit 0
"""


FAKE_ZERO = """#!/bin/sh
prev=""
outdir=""
last=""
for arg in "$@"; do
  if [ "$prev" = "--outdir" ]; then outdir="$arg"; fi
  prev="$arg"
  last="$arg"
done
stem=$(basename "$last" .docx)
: > "$outdir/$stem.pdf"
"""


def _script(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


def _docx(tmp_path: Path) -> Path:
    path = tmp_path / "input.docx"
    path.write_bytes(save(build_docx([("p", "Текст документа")])))
    return path


def test_render_pdf_returns_expected_path(tmp_path):
    soffice = _script(tmp_path, "soffice", FAKE_OK)
    docx = _docx(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = render_pdf(docx, out_dir, soffice=soffice, timeout_s=10)

    assert result == out_dir / "input.pdf"
    assert result.read_bytes().startswith(b"%PDF")


def test_render_pdf_creates_missing_out_dir(tmp_path):
    soffice = _script(tmp_path, "soffice", FAKE_OK)
    out_dir = tmp_path / "nested" / "out"

    result = render_pdf(_docx(tmp_path), out_dir, soffice=soffice, timeout_s=10)

    assert result.is_file()


def test_render_pdf_timeout_raises_pdf_error(tmp_path):
    soffice = _script(tmp_path, "soffice", FAKE_SLEEP)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(PdfError) as exc:
        render_pdf(_docx(tmp_path), out_dir, soffice=soffice, timeout_s=1)

    assert str(exc.value) == MSG


def test_render_pdf_nonzero_exit_raises_pdf_error(tmp_path):
    soffice = _script(tmp_path, "soffice", FAKE_FAIL)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(PdfError) as exc:
        render_pdf(_docx(tmp_path), out_dir, soffice=soffice, timeout_s=10)

    assert str(exc.value) == MSG


def test_render_pdf_missing_output_raises_pdf_error(tmp_path):
    soffice = _script(tmp_path, "soffice", FAKE_NO_OUTPUT)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(PdfError) as exc:
        render_pdf(_docx(tmp_path), out_dir, soffice=soffice, timeout_s=10)

    assert str(exc.value) == MSG


def test_render_pdf_missing_binary_raises_pdf_error(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(PdfError) as exc:
        render_pdf(
            _docx(tmp_path),
            out_dir,
            soffice=str(tmp_path / "no-such-soffice"),
            timeout_s=10,
        )

    assert str(exc.value) == MSG
    assert isinstance(exc.value.__cause__, OSError)


@pytest.mark.soffice
@pytest.mark.skipif(shutil.which("soffice") is None, reason="нет LibreOffice")
def test_render_pdf_with_real_libreoffice(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = render_pdf(_docx(tmp_path), out_dir, soffice="soffice", timeout_s=120)

    assert result == out_dir / "input.pdf"
    assert result.read_bytes().startswith(b"%PDF")


def test_render_pdf_zero_length_output_raises_pdf_error(tmp_path):
    soffice = _script(tmp_path, "soffice", FAKE_ZERO)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(PdfError):
        render_pdf(_docx(tmp_path), out_dir, soffice=soffice, timeout_s=10)


def test_render_pdf_timeout_kills_grandchildren(tmp_path):
    pidfile = tmp_path / "grandchild.pid"
    body = f"#!/bin/sh\nsleep 30 &\necho $! > {pidfile}\nsleep 30\n"
    soffice = _script(tmp_path, "soffice", body)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(PdfError):
        render_pdf(_docx(tmp_path), out_dir, soffice=soffice, timeout_s=1)

    pid = int(pidfile.read_text())
    deadline = time.monotonic() + 3
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        # зомби (если родитель-init ещё не собрал) считаем завершённым
        try:
            if "Z" in Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]:
                break
        except OSError:
            break
        assert time.monotonic() < deadline, "внук soffice остался жив"
        time.sleep(0.05)
