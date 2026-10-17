"""Построение PDF-предпросмотра из DOCX через LibreOffice (headless)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

PDF_ERROR_MESSAGE = "Не удалось построить PDF-предпросмотр"


class PdfError(Exception):
    pass


def render_pdf(docx_path: Path, out_dir: Path, *, soffice: str, timeout_s: int) -> Path:
    """Конвертирует DOCX в PDF в out_dir и возвращает путь к файлу.

    Каждый вызов использует собственный профиль LibreOffice, поэтому параллельные
    конвертации не конфликтуют между собой.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = out_dir / (docx_path.stem + ".pdf")
    with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile:
        cmd = [
            soffice,
            "--headless",
            f"-env:UserInstallation={Path(profile).as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(docx_path),
        ]
        try:
            proc = subprocess.run(cmd, timeout=timeout_s, capture_output=True, check=False)
        except subprocess.TimeoutExpired as exc:
            raise PdfError(PDF_ERROR_MESSAGE) from exc
        except OSError as exc:
            raise PdfError(PDF_ERROR_MESSAGE) from exc

    if proc.returncode != 0 or not expected.is_file():
        raise PdfError(PDF_ERROR_MESSAGE)
    return expected
