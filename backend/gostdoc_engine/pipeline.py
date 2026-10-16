"""Конвейер: загрузка, проверка, исправление, комментарии, сохранение."""

import io
from dataclasses import asdict, dataclass
from typing import Literal

from . import rules  # noqa: F401  (регистрация всех правил)
from .analyze import analyze
from .comments import add_comments
from .importer import load_docx, text_to_docx
from .profile import Profile
from .runner import run_check, run_fix
from .textguard import TextChangedError, normalized_words


@dataclass
class ProcessResult:
    docx_bytes: bytes
    report: dict


def process(data: bytes | str, profile: Profile, mode: Literal["check", "format"]) -> ProcessResult:
    doc = text_to_docx(data) if isinstance(data, str) else load_docx(data)
    model = analyze(doc)
    failed: list[str] = []
    if mode == "format":
        before = normalized_words(model)
        failed.extend(run_fix(model, profile))
        model = analyze(doc)
        if normalized_words(model) != before:
            raise TextChangedError("Текст документа изменился при оформлении")
    result = run_check(model, profile)
    failed.extend(result.failed_rules)
    add_comments(model, result.issues)
    buf = io.BytesIO()
    doc.save(buf)
    report = {
        "profile": profile.id,
        "mode": mode,
        "issues": [asdict(i) for i in result.issues],
        "failed_rules": list(dict.fromkeys(failed)),
        "summary": {
            "errors": sum(i.severity == "error" for i in result.issues),
            "recommendations": sum(i.severity == "recommendation" for i in result.issues),
        },
    }
    return ProcessResult(buf.getvalue(), report)
