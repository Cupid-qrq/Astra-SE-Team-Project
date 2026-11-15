import json

import pytest

from app.shared.presentation import PresentationNames


def test_titles_are_projected_without_changing_sources_or_storage_fields():
    names = PresentationNames({"成绩与重评验收": "第一单元综合练习"})
    value = {
        "assignment_id": "id",
        "title": "成绩与重评验收",
        "items": [{"title": "未知题目"}],
        "body": "成绩与重评验收",
        "code": "成绩与重评验收",
        "checksum": "abc",
    }
    result = names.project(value)
    assert result["title"] == "第一单元综合练习"
    assert value["title"] == "成绩与重评验收"
    assert result["body"] == result["code"] == "成绩与重评验收"
    assert result["items"] == value["items"] and result["checksum"] == "abc"
    assert PresentationNames({}).project(value) is value


def test_configuration_is_explicit_and_invalid_labels_are_rejected(tmp_path):
    path = tmp_path / "names.json"
    path.write_text(json.dumps({"课程演示": "程序设计基础"}), encoding="utf-8")
    assert (
        PresentationNames.from_file(str(path)).project([{"title": "课程演示"}])[0]["title"]
        == "程序设计基础"
    )
    assert PresentationNames.from_file(None).project({"title": "课程演示"}) == {"title": "课程演示"}
    path.write_text(json.dumps({"课程演示": {"title": "bad"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        PresentationNames.from_file(str(path))


def test_replacement_respects_the_shortest_title_contract():
    assert PresentationNames({"old": "题" * 100}).project({"title": "old"})["title"] == "题" * 100
    with pytest.raises(ValueError):
        PresentationNames({"old": "题" * 101})
