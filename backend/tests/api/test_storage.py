import uuid
from types import SimpleNamespace

import pytest

from gostdoc_api import storage


def _settings(tmp_path):
    return SimpleNamespace(storage_dir=str(tmp_path / "storage"))


def test_job_dir_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        storage.job_dir(_settings(tmp_path), "../x")


@pytest.mark.parametrize(
    "job_id",
    [
        str(uuid.uuid1()),  # не версия 4
        str(uuid.uuid4()).upper(),  # не каноническая форма
        "not-a-uuid",
        "",
    ],
)
def test_job_dir_rejects_non_canonical_uuid4(tmp_path, job_id):
    with pytest.raises(ValueError):
        storage.job_dir(_settings(tmp_path), job_id)


def test_job_dir_creates_directory_under_jobs(tmp_path):
    settings = _settings(tmp_path)
    job_id = str(uuid.uuid4())
    path = storage.job_dir(settings, job_id)
    assert path == tmp_path / "storage" / "jobs" / job_id
    assert path.is_dir()


def test_write_stores_bytes(tmp_path):
    target = tmp_path / "input.docx"
    storage.write(target, b"abc")
    assert target.read_bytes() == b"abc"


def test_delete_job_files_removes_directory(tmp_path):
    settings = _settings(tmp_path)
    job_id = str(uuid.uuid4())
    path = storage.job_dir(settings, job_id)
    storage.write(path / "result.pdf", b"%PDF")
    storage.delete_job_files(settings, job_id)
    assert not path.exists()


def test_delete_job_files_is_noop_when_missing(tmp_path):
    storage.delete_job_files(_settings(tmp_path), str(uuid.uuid4()))


def test_delete_job_files_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        storage.delete_job_files(_settings(tmp_path), "../x")
