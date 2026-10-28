"""Все тексты бота."""

from __future__ import annotations

START = "Привет! Я оформляю и проверяю документы по ГОСТ. Что делаем?"
MENU = "Главное меню"
RESTART = "Начните заново"
SOON = "Этот раздел скоро появится"
HELP = (
    "Я проверяю и оформляю DOCX-документы по ГОСТ.\n\n"
    "Пришлите DOCX-файл (до 20 МБ) или вставьте текст сообщением, выберите профиль "
    "требований и режим: проверка оставит комментарии, оформление исправит документ."
)
HELP_SITE = "Подробнее и все замечания — на сайте: {url}"

SEND_DOC = "Пришлите DOCX-файл или вставьте текст сообщением"
TEXT_ACCEPTED = "Текст принят ({n} симв.). Можно прислать ещё или нажать «Готово»"
FILE_TOO_BIG = "Файл больше 20 МБ"
CHOOSE_PROFILE = "Выберите профиль требований"
CHOOSE_MODE = "Что сделать с документом?"
QUEUED = "В очереди…"
PROCESSING = "Обрабатываем…"
JOB_FAILED = "Не удалось обработать документ"
JOB_TIMEOUT = "Обработка заняла слишком много времени, попробуйте позже"
JOB_EXPIRED = "Срок хранения результата истёк"
NO_PROFILES = "Нет доступных профилей"
FILES_FAILED = "Результат готов, но файлы получить не удалось"

ISSUES_HEAD = "Первые {n} замечаний:"
CHECK_NONE = "Замечаний нет"
FORMAT_NONE = "Оформление готово. Замечаний не осталось"


def plural(n: int) -> str:
    m10, m100 = n % 10, n % 100
    if m10 == 1 and m100 != 11:
        return "замечание"
    if 2 <= m10 <= 4 and not 12 <= m100 <= 14:
        return "замечания"
    return "замечаний"


def summary(report: dict | None, mode: str) -> str:
    """Сводка по отчёту; в режиме оформления остаются только невыправленные замечания."""
    report = report or {}
    s = report.get("summary") or {}
    if "errors" in s or "recommendations" in s:
        n = s.get("errors", 0) + s.get("recommendations", 0)
    else:
        n = len(report.get("issues") or [])
    if n == 0:
        return CHECK_NONE if mode == "check" else FORMAT_NONE
    if mode == "check":
        return f"{n} {plural(n)}"
    return f"Оформление готово. {n} {plural(n)} требуют вашего решения"
