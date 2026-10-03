import uuid

import pytest

from app.models.resourceModel import ResourceLessonModel, ResourceModel, ResourceModuleModel

VIDEO_URL = "https://www.youtube.com/watch?v=LoW3vFu8TH4"
VIDEO_NOTES = "Build a repeatable process to identify employers near you."


@pytest.mark.asyncio
async def test_resource_detail_decodes_video_lessons(client, auth_headers, db_session):
    # Stored the way `scripts/seed_resources.py` writes it: the legacy
    # "url\nnotes" string, not the codec's JSON envelope.
    resource = ResourceModel(
        id=uuid.uuid4(),
        title="LinkedIn Hidden Job Market Playbook",
        description="Find hiring managers.",
        category="Career",
        is_published=True,
    )
    module = ResourceModuleModel(id=uuid.uuid4(), resource_id=resource.id, title="Module 1", position=1)
    lesson = ResourceLessonModel(
        id=uuid.uuid4(),
        module_id=module.id,
        title="How to Find Employers in your Hometown",
        position=1,
        content_type="video_url",
        content=f"{VIDEO_URL}\n{VIDEO_NOTES}",
    )
    db_session.add_all([resource, module, lesson])
    await db_session.commit()

    response = await client.get(f"/api/v1/resources/{resource.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["is_published"] is True
    served = body["modules"][0]["lessons"][0]
    assert served["content_type"] == "video_url"
    assert served["video_url"] == VIDEO_URL
    assert served["notes"] == VIDEO_NOTES
    assert served["content_payload"] == {"video_url": VIDEO_URL, "notes": VIDEO_NOTES}
