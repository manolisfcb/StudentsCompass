from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LessonContentEnvelope:
    content_type: str
    payload: dict[str, str]
    storage_content: str
    legacy_content: str


class ResourceLessonContentCodec:
    """
    Canonical serializer/deserializer for resource lesson content.

    We keep storage in the existing `resource_lessons.content` column but store
    a structured JSON envelope, so backend/frontend can differentiate URL vs
    notes/body in a stable way.
    """

    VERSION = 2
    VIDEO_TYPES = {"video_url"}
    LINK_TYPES = {"external_link", "pdf_url", "ppt_url"}
    TEXT_TYPES = {"text", "html"}
    SPECIAL_TYPES = {"resume_upload"}
    DEFAULT_TYPE = "text"
    SUPPORTED_TYPES = VIDEO_TYPES | LINK_TYPES | TEXT_TYPES | SPECIAL_TYPES

    def normalize_content_type(self, content_type: str | None) -> str:
        value = (content_type or self.DEFAULT_TYPE).strip().lower()
        return value if value in self.SUPPORTED_TYPES else self.DEFAULT_TYPE

    @staticmethod
    def _clean(value: str | None) -> str:
        return (value or "").strip()

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        lowered = value.strip().lower()
        return lowered.startswith("http://") or lowered.startswith("https://")

    def _build_payload(
        self,
        *,
        content_type: str,
        content: str | None,
        video_url: str | None,
        resource_url: str | None,
        notes: str | None,
    ) -> dict[str, str]:
        body = self._clean(content)
        note_text = self._clean(notes)
        video = self._clean(video_url)
        resource = self._clean(resource_url)

        if content_type in self.VIDEO_TYPES:
            if not video and self._looks_like_url(body):
                video = body
                body = ""
            if not note_text and body and not self._looks_like_url(body):
                note_text = body
            if not video:
                raise ValueError("Video lessons require a valid video URL.")
            payload = {"video_url": video}
            if note_text:
                payload["notes"] = note_text
            return payload

        if content_type in self.LINK_TYPES:
            if not resource and self._looks_like_url(body):
                resource = body
                body = ""
            if not resource:
                raise ValueError("Link lessons require a valid resource URL.")
            payload = {"resource_url": resource}
            if note_text:
                payload["notes"] = note_text
            if body:
                payload["body"] = body
            return payload

        if content_type in self.SPECIAL_TYPES:
            # For resume upload we persist guidance text in body.
            prompt = body or note_text or "Upload your resume and receive AI feedback."
            payload = {"body": prompt}
            if note_text and note_text != prompt:
                payload["notes"] = note_text
            return payload

        # text/html default
        payload = {"body": body}
        if note_text:
            payload["notes"] = note_text
        return payload

    def _encode_storage(self, *, content_type: str, payload: dict[str, str]) -> str:
        envelope = {
            "version": self.VERSION,
            "type": content_type,
            "payload": payload,
        }
        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))

    def _legacy_content(self, *, content_type: str, payload: dict[str, str]) -> str:
        if content_type in self.VIDEO_TYPES:
            url = payload.get("video_url", "")
            notes = payload.get("notes", "")
            if url and notes:
                return f"{url}\n{notes}"
            return url or notes

        if content_type in self.LINK_TYPES:
            return payload.get("resource_url") or payload.get("body", "")

        return payload.get("body") or payload.get("notes", "")

    def encode(
        self,
        *,
        content_type: str | None,
        content: str | None,
        video_url: str | None = None,
        resource_url: str | None = None,
        notes: str | None = None,
    ) -> LessonContentEnvelope:
        normalized_type = self.normalize_content_type(content_type)
        payload = self._build_payload(
            content_type=normalized_type,
            content=content,
            video_url=video_url,
            resource_url=resource_url,
            notes=notes,
        )
        storage_content = self._encode_storage(content_type=normalized_type, payload=payload)
        legacy_content = self._legacy_content(content_type=normalized_type, payload=payload)
        return LessonContentEnvelope(
            content_type=normalized_type,
            payload=payload,
            storage_content=storage_content,
            legacy_content=legacy_content,
        )

    def _decode_legacy(self, *, content_type: str, raw_content: str) -> dict[str, str]:
        content = self._clean(raw_content)
        if not content:
            return {}

        if content_type in self.VIDEO_TYPES:
            if content.startswith("{") and content.endswith("}"):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        url = self._clean(str(parsed.get("url", "")))
                        description = self._clean(str(parsed.get("description", "")))
                        payload: dict[str, str] = {}
                        if url:
                            payload["video_url"] = url
                        if description:
                            payload["notes"] = description
                        if payload:
                            return payload
                except Exception:
                    pass

            lines = [line.strip() for line in content.splitlines() if line.strip()]
            first_url = next((line for line in lines if self._looks_like_url(line)), "")
            if first_url:
                notes = " ".join(line for line in lines if line != first_url).strip()
                payload = {"video_url": first_url}
                if notes:
                    payload["notes"] = notes
                return payload

            return {"notes": content}

        if content_type in self.LINK_TYPES:
            if self._looks_like_url(content):
                return {"resource_url": content}
            return {"body": content}

        return {"body": content}

    def decode(self, *, content_type: str | None, raw_content: str | None) -> LessonContentEnvelope:
        normalized_type = self.normalize_content_type(content_type)
        content = self._clean(raw_content)
        payload: dict[str, str] = {}

        if content.startswith("{") and content.endswith("}"):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    parsed_type = self.normalize_content_type(str(parsed.get("type", normalized_type)))
                    parsed_payload = parsed.get("payload")
                    if isinstance(parsed_payload, dict):
                        cleaned_payload: dict[str, str] = {}
                        for key, value in parsed_payload.items():
                            if value is None:
                                continue
                            cleaned_value = self._clean(str(value))
                            if cleaned_value:
                                cleaned_payload[str(key)] = cleaned_value
                        if cleaned_payload:
                            normalized_type = parsed_type
                            payload = cleaned_payload
            except Exception:
                payload = {}

        if not payload:
            payload = self._decode_legacy(content_type=normalized_type, raw_content=content)

        storage_content = self._encode_storage(content_type=normalized_type, payload=payload)
        legacy_content = self._legacy_content(content_type=normalized_type, payload=payload)
        return LessonContentEnvelope(
            content_type=normalized_type,
            payload=payload,
            storage_content=storage_content,
            legacy_content=legacy_content,
        )

    def to_api_fields(self, *, content_type: str | None, raw_content: str | None) -> dict[str, Any]:
        decoded = self.decode(content_type=content_type, raw_content=raw_content)
        return {
            "content_type": decoded.content_type,
            "content": decoded.legacy_content,
            "content_payload": decoded.payload,
            "video_url": decoded.payload.get("video_url"),
            "resource_url": decoded.payload.get("resource_url"),
            "notes": decoded.payload.get("notes"),
        }
