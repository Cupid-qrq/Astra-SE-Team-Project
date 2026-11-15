import json

from sqlalchemy import text
from test_http import http_env as http_env
from test_http import login

from app.main import create_app


def test_names_apply_to_authorized_gets_and_default_deployment_keeps_names(
    http_env, tmp_path, monkeypatch
):
    engine, ids, settings, normal = http_env
    config = tmp_path / "names.json"
    config.write_text(json.dumps({"test": "第一单元综合练习"}), encoding="utf-8")
    monkeypatch.setenv("ASTRA_PRESENTATION_NAMES_FILE", str(config))
    app = create_app(settings, engine=engine)
    client = login(app, "student")
    path = "/api/v1/assignments/" + ids["assignment"]
    result = client.get(path)
    assert result.status_code == 200, result.text
    assert result.json()["title"] == "第一单元综合练习"
    assert result.json()["assignment_id"] == ids["assignment"]
    assert login(app, "admin").get(path).status_code == 403
    assert login(normal, "student").get(path).json()["title"] == "test"
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT title FROM assignments WHERE assignment_id=:id"),
                {"id": ids["assignment"]},
            )
            == "test"
        )
