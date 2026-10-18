"""Ручная проверка извлечения: python scripts/try_extraction.py методичка.docx

Ключ и адрес модели берутся из окружения (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL).
"""

from __future__ import annotations

import sys
from pathlib import Path

from gostdoc_api.config import get_settings
from gostdoc_api.extraction import run_extraction
from gostdoc_api.guideline_text import check_text, extract_text


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Использование: try_extraction.py <файл.docx|файл.pdf>")
        return 2
    settings = get_settings()
    if not settings.llm_api_key:
        print("Не задан LLM_API_KEY")
        return 2
    path = Path(argv[1])
    text = check_text(extract_text(path.read_bytes(), path.name))
    result = run_extraction(text, settings)
    print(f"{'Правило':<24}{'Поле':<24}{'Значение':<18}{'Стр.':<6}Цитата")
    for f in result["found"]:
        page = f["page"] if f["page"] is not None else "-"
        quote = f["quote"].replace("\n", " ")[:80]
        print(f"{f['rule']:<24}{f['path']:<24}{f['value']!s:<18}{page!s:<6}{quote}")
    if result["unsupported"]:
        print("\nНе поддерживается:")
        for u in result["unsupported"]:
            print(f"- {u['text']} (стр. {u['page'] or '-'})")
    print(f"\nНайдено: {len(result['found'])}, отброшено: {result['rejected_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
