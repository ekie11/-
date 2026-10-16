"""CLI: python -m gostdoc_engine IN [--text] [--profile ID|path.json] --mode check|format -o OUT."""

import argparse
import json
import sys
from pathlib import Path

import pydantic

from .importer import InputError
from .pipeline import process
from .profile import builtin_profile, load_profile
from .textguard import TextChangedError


def _profile(arg: str):
    if arg.endswith(".json") or Path(arg).exists():
        return load_profile(Path(arg))
    return builtin_profile(arg)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gostdoc_engine")
    ap.add_argument("input")
    ap.add_argument("--text", action="store_true", help="вход — обычный текст")
    ap.add_argument("--profile", default="gost-7.32-2017")
    ap.add_argument("--mode", choices=["check", "format"], required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--report")
    args = ap.parse_args(argv)
    try:
        profile = _profile(args.profile)
        path = Path(args.input)
        data = path.read_text(encoding="utf-8") if args.text else path.read_bytes()
        result = process(data, profile, args.mode)
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Ошибка: файл не найден: {exc.filename}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("Ошибка: входной текст должен быть в кодировке UTF-8", file=sys.stderr)
        return 2
    except TextChangedError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    except pydantic.ValidationError:
        print("Ошибка: некорректный JSON-профиль", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    Path(args.output).write_bytes(result.docx_bytes)
    if args.report:
        Path(args.report).write_text(
            json.dumps(result.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
