"""Live preview: render a scene document + sample data to a 6x22 character grid.

Pure render reuse (``Scene.from_dict`` + ``render_scene`` + ``to_characters``) — no
board, no rate limit — so it is safe to call straight from the request handler. The
frontend draws the returned ints; this is the same grid the real board would show.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...render import render_scene
from ...scene import Scene as SceneDoc
from ..deps import CurrentUser, SettingsDep
from ..schemas import PreviewIn, PreviewOut

router = APIRouter(tags=["preview"])


@router.post("/preview", response_model=PreviewOut)
def preview(body: PreviewIn, user: CurrentUser, settings: SettingsDep) -> PreviewOut:
    try:
        scene = SceneDoc.from_dict(body.document)
        render_scene(scene, body.sample_data, settings)
        characters = scene.to_characters()
    except (KeyError, ValueError, TypeError) as exc:
        # Structured detail: a missing sample_data key raises KeyError(key); expose it
        # cleanly so the client can seed it without regex-parsing the message.
        missing_key = exc.args[0] if isinstance(exc, KeyError) and exc.args else None
        detail = {"message": f"cannot render scene: {exc}", "missing_key": missing_key}
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail) from exc
    return PreviewOut(rows=len(characters), cols=len(characters[0]) if characters else 0, characters=characters)
