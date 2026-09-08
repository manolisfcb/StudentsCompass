import pytest

from app import template_utils


def test_asset_url_appends_a_version_and_refreshes_on_change(tmp_path, monkeypatch):
    static_root = tmp_path / "static"
    css_file = static_root / "css" / "style.css"
    css_file.parent.mkdir(parents=True)
    css_file.write_text("body { color: red; }", encoding="utf-8")

    monkeypatch.setattr(template_utils, "STATIC_ROOT", static_root)
    template_utils._build_asset_version.cache_clear()

    first_url = template_utils.asset_url("css/style.css")

    css_file.write_text("body { color: royalblue; }", encoding="utf-8")
    second_url = template_utils.asset_url("css/style.css")

    assert first_url.startswith("/static/css/style.css?v=")
    assert second_url.startswith("/static/css/style.css?v=")
    assert first_url != second_url


def test_asset_url_falls_back_when_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(template_utils, "STATIC_ROOT", tmp_path / "static")
    template_utils._build_asset_version.cache_clear()
    template_utils._read_asset_text.cache_clear()

    assert template_utils.asset_url("css/missing.css") == "/static/css/missing.css"


def test_inline_asset_returns_stylesheet_contents(tmp_path, monkeypatch):
    static_root = tmp_path / "static"
    css_file = static_root / "css" / "style.css"
    css_file.parent.mkdir(parents=True)
    css_file.write_text("body { color: red; }", encoding="utf-8")

    monkeypatch.setattr(template_utils, "STATIC_ROOT", static_root)
    template_utils._read_asset_text.cache_clear()

    assert str(template_utils.inline_asset("css/style.css")) == "body { color: red; }"


@pytest.mark.asyncio
async def test_homepage_renders_versioned_assets(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert "<style>" in response.text
    assert "Career Readiness, Rebuilt" in response.text
    assert '/static/css/style.css?v=' not in response.text
    assert '/static/css/home.css?v=' not in response.text
