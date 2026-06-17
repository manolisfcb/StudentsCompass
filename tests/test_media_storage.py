import pytest

from app.services.mediaStorageService import get_media_storage_provider, get_media_storage_service


def test_media_storage_provider_defaults_to_imagekit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEDIA_STORAGE_PROVIDER", raising=False)

    assert get_media_storage_provider() == "imagekit"


def test_media_storage_service_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported media storage provider"):
        get_media_storage_service(provider="unknown")
