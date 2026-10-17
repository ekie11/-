"""Построение PDF-предпросмотра из DOCX через LibreOffice (headless)."""

from __future__ import annotations

import os
import signal
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
    with tempfile.TemporaryDirectory(prefix="lo-profile-", ignore_cleanup_errors=True) as profile:
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
            # Отдельная сессия: soffice порождает дочерние процессы, убиваем всю группу
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            raise PdfError(PDF_ERROR_MESSAGE) from exc
        try:
            proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _kill_group(proc)
            raise PdfError(PDF_ERROR_MESSAGE) from exc
        except BaseException as exc:  # в т.ч. JobTimeoutException из RQ
            _kill_group(proc)
            if isinstance(exc, Exception):
                raise PdfError(PDF_ERROR_MESSAGE) from exc
            raise
        # Даже после успешного выхода убираем возможных осиротевших потомков
        _kill_group(proc)

    if proc.returncode != 0 or not expected.is_file() or expected.stat().st_size == 0:
        raise PdfError(PDF_ERROR_MESSAGE)
    return expected


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()
