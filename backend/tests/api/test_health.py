def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_defaults(settings):
    assert settings.cookie_secure is False
    assert settings.soffice_path == "soffice"
    assert settings.job_timeout_s == 120
    assert settings.file_ttl_days == 30
