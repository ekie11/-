"""Номера страниц оглавления и PDF через headless LibreOffice (UNO)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .pdf import PDF_ERROR_MESSAGE, PdfError, _kill_group

SCRIPT = Path(__file__).with_name("lo_uno_script.py")


def page_numbers_and_pdf(
    docx_path: Path, out_pdf: Path, *, soffice: str, timeout_s: int
) -> dict[str, int]:
    """Обновляет индексы в копии DOCX, возвращает {закладка _Toc…: страница}, пишет PDF в out_pdf.

    Оригинал не изменяется. При любой ошибке — PdfError.
    """
    python = os.environ.get("LO_PYTHON", "python3")
    script = os.environ.get("LO_UNO_SCRIPT", str(SCRIPT))
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lo-pages-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        copy = work / "doc.docx"
        profile = work / "profile"
        tmp_pdf = work / "out.pdf"
        try:
            shutil.copyfile(docx_path, copy)
            proc = subprocess.Popen(
                [python, script, soffice, str(profile), str(copy), str(tmp_pdf)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            raise PdfError(PDF_ERROR_MESSAGE) from exc
        try:
            stdout, _ = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _kill_group(proc)
            raise PdfError(PDF_ERROR_MESSAGE) from exc
        except BaseException as exc:  # в т.ч. JobTimeoutException из RQ
            _kill_group(proc)
            if isinstance(exc, Exception):
                raise PdfError(PDF_ERROR_MESSAGE) from exc
            raise
        _kill_group(proc)
        if proc.returncode != 0 or not tmp_pdf.is_file() or tmp_pdf.stat().st_size == 0:
            raise PdfError(PDF_ERROR_MESSAGE)
        try:
            raw = json.loads(stdout.decode("utf-8"))
            pages = {str(k): int(v) for k, v in raw.items()}
        except (ValueError, AttributeError, TypeError) as exc:
            raise PdfError(PDF_ERROR_MESSAGE) from exc
        shutil.move(str(tmp_pdf), out_pdf)
    return pages
