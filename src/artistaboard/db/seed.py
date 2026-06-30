"""Seed the bundled ``scenes/*.json`` as shared, read-only system templates.

Idempotent by name: a system scene that already exists is left untouched, so this
is safe to run on every startup. Users start from these and clone-on-edit.
"""

from __future__ import annotations

import json

from sqlmodel import Session, select

from ..config import Settings
from ..render import scene_variables
from .models import Scene


def seed_system_scenes(session: Session, settings: Settings) -> int:
    existing = set(session.exec(select(Scene.name).where(Scene.is_system)).all())
    added = 0
    for path in sorted(settings.scenes_dir.glob("*.json")):
        name = path.stem
        if name in existing:
            continue
        document = json.loads(path.read_text())
        session.add(
            Scene(
                owner_id=None,
                name=name,
                description=f"Bundled {name} template",
                is_system=True,
                document=document,
                required_variables=scene_variables(document),
            )
        )
        added += 1
    if added:
        session.commit()
    return added
