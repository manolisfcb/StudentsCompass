"""The model manifest must actually cover every mapped model.

``Base.metadata`` is only as complete as the import list that built it, and
Alembic decides what to create — and what to *drop* — from that metadata. When
``roadmapModel`` was missing from Alembic's own list, autogenerate could not see
the roadmap tables at all; a migration generated in that state would have
proposed dropping them.

These tests run on the fast lane: they only inspect metadata, no database.
"""
from __future__ import annotations

import importlib
import pkgutil

import pytest

from app.db import Base
from app.models import registry


def _mapped_classes_in_module(module):
    """Every declarative class this module defines (not ones it imported)."""
    found = []
    for name in dir(module):
        candidate = getattr(module, name)
        if not isinstance(candidate, type) or not issubclass(candidate, Base):
            continue
        if candidate is Base or getattr(candidate, "__tablename__", None) is None:
            continue
        if candidate.__module__ != module.__name__:
            continue
        found.append(candidate)
    return found


def _all_model_modules():
    import app.models

    return [
        importlib.import_module(f"app.models.{info.name}")
        for info in pkgutil.iter_modules(app.models.__path__)
        if info.name not in {"registry"}
    ]


def test_every_mapped_model_is_in_the_manifest():
    registered = set(registry.ALL_MODELS)
    missing = {
        model
        for module in _all_model_modules()
        for model in _mapped_classes_in_module(module)
        if model not in registered
    }

    assert not missing, (
        "These models are mapped but absent from app/models/registry.ALL_MODELS, "
        "so autogenerate would not see their tables: "
        + ", ".join(sorted(model.__name__ for model in missing))
    )


def test_manifest_entries_are_all_mapped():
    """A stale entry would keep a deleted model's table alive in metadata."""
    for model in registry.ALL_MODELS:
        assert issubclass(model, Base)
        assert getattr(model, "__tablename__", None)


@pytest.mark.parametrize(
    "table_name",
    [
        # Previously invisible to Alembic because env.py never imported the
        # module that maps them.
        "roadmaps",
        "user_roadmaps",
        "user_task_progress",
        "resume_course_evaluations",
        # Created by a migration and never mapped at all.
        "resource_enrollments",
    ],
)
def test_previously_unmapped_tables_are_in_metadata(table_name):
    registry.import_all_models()
    assert table_name in Base.metadata.tables


def test_resource_lesson_progress_maps_the_converged_shape():
    """The union of both migration branches, so either database converges."""
    registry.import_all_models()
    table = Base.metadata.tables["resource_lesson_progress"]

    assert "resource_id" in table.columns
    # Nullable because the writer derives the resource from the lesson and does
    # not set it; making it NOT NULL is a separate forward-only step.
    assert table.columns["resource_id"].nullable is True
    assert table.columns["completed_at"].nullable is True
    assert table.columns["last_opened_at"].nullable is True
    assert {"created_at", "updated_at"} <= set(table.columns.keys())
