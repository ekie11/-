from datetime import UTC, datetime, timedelta

from gostdoc_api import storage
from gostdoc_api.cleanup import cleanup_expired
from gostdoc_api.models import Job, SessionToken, User

from .test_jobs import fake_pdf, post, queue, redis_conn  # noqa: F401
from .test_profiles import GOST, reg

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _job(client, db_session, settings, text="Текст работы."):
    r = post(client, data={"mode": "format", "text": text, "profile_id": GOST})
    assert r.status_code == 202
    return r.json()["id"]


def test_expired_job_files_removed_and_410(client, queue, db_session, settings):  # noqa: F811
    reg(client)
    jid = _job(client, db_session, settings)
    job = db_session.get(Job, jid)
    assert job.status == "done"
    job.expires_at = NOW - timedelta(days=1)
    db_session.commit()
    job_path = storage.job_dir(settings, jid)
    assert job_path.exists()

    assert cleanup_expired(db_session, settings, NOW) == 1

    assert not job_path.exists()
    db_session.expire_all()
    job = db_session.get(Job, jid)
    assert job.status == "expired"
    assert job.input_path is None and job.output_docx is None and job.output_pdf is None
    assert client.get(f"/jobs/{jid}/docx").status_code == 410
    assert client.get(f"/jobs/{jid}").json()["status"] == "expired"
    # повторный запуск ничего не делает
    assert cleanup_expired(db_session, settings, NOW) == 0


def test_fresh_job_untouched(client, queue, db_session, settings):  # noqa: F811
    reg(client)
    jid = _job(client, db_session, settings)
    assert cleanup_expired(db_session, settings, NOW) == 0
    # expires_at = сейчас + 30 дней > NOW(2026-10-17)? берём реальное «сейчас»
    assert cleanup_expired(db_session, settings, datetime.now(UTC)) == 0
    db_session.expire_all()
    assert db_session.get(Job, jid).status == "done"
    assert client.get(f"/jobs/{jid}/docx").status_code == 200


def test_expired_session_removed(client, db_session, settings):
    reg(client)
    user = db_session.query(User).one()
    db_session.add(
        SessionToken(user_id=user.id, token_hash="x" * 64, expires_at=NOW - timedelta(seconds=1))
    )
    db_session.commit()
    assert db_session.query(SessionToken).count() == 2
    cleanup_expired(db_session, settings, datetime.now(UTC))
    hashes = [s.token_hash for s in db_session.query(SessionToken)]
    assert "x" * 64 not in hashes and len(hashes) == 1
    assert client.get("/auth/me").status_code == 200


def test_stuck_extractions_marked_failed(client, db_session, settings):
    reg(client)
    from datetime import timedelta

    from gostdoc_api.llm import extraction_timeout_s
    from gostdoc_api.models import Extraction

    over = timedelta(seconds=extraction_timeout_s(settings)) + timedelta(minutes=6)
    rows = [
        # (id, status, created_at, started_at)
        ("run_old", "running", NOW - timedelta(days=1), NOW - over),
        ("run_new", "running", NOW - timedelta(hours=2), NOW - timedelta(minutes=2)),
        ("q_old", "queued", NOW - timedelta(hours=25), None),
        ("q_1h", "queued", NOW - timedelta(hours=3), None),
        ("done", "done", NOW - timedelta(days=1), None),
    ]
    for i, st, created, started in rows:
        db_session.add(
            Extraction(id=i, user_id=1, status=st, base_profile_id="x",
                       created_at=created, started_at=started)
        )
    db_session.commit()
    cleanup_expired(db_session, settings, NOW)
    db_session.expire_all()
    for i in ("run_old", "q_old"):
        row = db_session.get(Extraction, i)
        assert row.status == "failed" and row.counts_toward_limit is False
        assert "временно недоступен" in row.error
    assert db_session.get(Extraction, "run_new").status == "running"
    assert db_session.get(Extraction, "q_1h").status == "queued"
    assert db_session.get(Extraction, "done").status == "done"


def test_stuck_threshold_covers_extraction_timeout(settings):
    from gostdoc_api.cleanup import running_stuck_after
    from gostdoc_api.llm import extraction_timeout_s

    assert running_stuck_after(settings).total_seconds() > extraction_timeout_s(settings)
