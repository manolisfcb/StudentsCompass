from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from fastapi.templating import Jinja2Templates

STATIC_ROOT = Path(__file__).resolve().parent / "static"


def configure_template_helpers(templates: Jinja2Templates) -> Jinja2Templates:
    templates.env.globals["asset_url"] = asset_url
    return templates


def asset_url(path: str) -> str:
    normalized_path = path.lstrip("/")
    version = _resolve_asset_version(normalized_path)
    url = f"/static/{normalized_path}"
    if not version:
        return url
    return f"{url}?v={version}"


def _resolve_asset_version(path: str) -> str | None:
    asset_path = (STATIC_ROOT / path).resolve()
    if not asset_path.is_file() or not asset_path.is_relative_to(STATIC_ROOT.resolve()):
        return None

    stat = asset_path.stat()
    return _build_asset_version(path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=256)
def _build_asset_version(path: str, mtime_ns: int, size: int) -> str:
    asset_path = STATIC_ROOT / path
    digest = sha256(asset_path.read_bytes()).hexdigest()
    return digest[:12]
