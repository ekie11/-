from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[2]


def test_migrations_create_all_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "gostdoc_api" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"users", "session_tokens", "profiles", "jobs", "extractions"} <= tables


def test_migration_0002_guest_mode(tmp_path):
    url = f"sqlite:///{tmp_path / 'mig2.db'}"
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "gostdoc_api" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0001")
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    assert "guest_sessions" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("jobs")}
    assert {"guest_id", "client_ip"} <= set(cols)
    assert cols["user_id"]["nullable"] is True
    command.downgrade(cfg, "0001")
