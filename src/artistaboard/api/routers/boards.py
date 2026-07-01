"""Board CRUD + run control. The Read/Write key is encrypted at rest and never
returned. Start/stop flip the BoardRun row then ask the BoardManager to reconcile
its workers; the worker (not the request) owns all board I/O and the rate limit.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from ...client import VestaboardClient, VestaboardError
from ...crypto import decrypt, encrypt
from ...db import Board, BoardRun, Pipeline
from ..deps import CurrentUser, SessionDep, SettingsDep
from ..schemas import BoardIn, BoardOut, BoardRunOut

router = APIRouter(prefix="/boards", tags=["boards"])


def _own_board(session: SessionDep, board_id: str, user_id: str) -> Board:
    board = session.get(Board, board_id)
    if board is None or board.owner_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "board not found")
    return board


def _apply_key(board: Board, rw_key: str, settings: SettingsDep) -> None:
    board.rw_key_encrypted = encrypt(rw_key, settings.encryption_secret)
    board.rw_key_last4 = rw_key[-4:]
    board.status = "ok"


@router.get("", response_model=list[BoardOut])
def list_boards(user: CurrentUser, session: SessionDep) -> list[BoardOut]:
    rows = session.exec(select(Board).where(Board.owner_id == user.id)).all()
    return [BoardOut.of(b) for b in rows]


@router.post("", response_model=BoardOut, status_code=status.HTTP_201_CREATED)
def create_board(body: BoardIn, user: CurrentUser, session: SessionDep, settings: SettingsDep) -> BoardOut:
    board = Board(owner_id=user.id, name=body.name, model=body.model, min_send_interval=body.min_send_interval)
    if body.rw_key:
        _apply_key(board, body.rw_key, settings)
    session.add(board)
    session.commit()
    session.refresh(board)
    return BoardOut.of(board)


@router.get("/{board_id}", response_model=BoardOut)
def get_board(board_id: str, user: CurrentUser, session: SessionDep) -> BoardOut:
    return BoardOut.of(_own_board(session, board_id, user.id))


@router.put("/{board_id}", response_model=BoardOut)
def update_board(
    board_id: str, body: BoardIn, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> BoardOut:
    board = _own_board(session, board_id, user.id)
    board.name = body.name
    board.model = body.model
    board.min_send_interval = body.min_send_interval
    if body.rw_key:  # only replace the key when a new one is supplied
        _apply_key(board, body.rw_key, settings)
    session.add(board)
    session.commit()
    session.refresh(board)
    return BoardOut.of(board)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: str, user: CurrentUser, session: SessionDep) -> None:
    board = _own_board(session, board_id, user.id)
    run = session.get(BoardRun, board_id)
    if run is not None:
        session.delete(run)
    session.delete(board)
    session.commit()


@router.post("/{board_id}/test", response_model=BoardOut)
def test_connection(board_id: str, user: CurrentUser, session: SessionDep, settings: SettingsDep) -> BoardOut:
    board = _own_board(session, board_id, user.id)
    if not board.rw_key_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "board has no key")
    key = decrypt(board.rw_key_encrypted, settings.encryption_secret)
    try:
        with VestaboardClient(key) as client:
            client.read()
        board.status = "ok"
    except VestaboardError:
        board.status = "unreachable"
    session.add(board)
    session.commit()
    session.refresh(board)
    return BoardOut.of(board)


@router.post("/{board_id}/assign", response_model=BoardRunOut)
def assign(board_id: str, pipeline_id: str, user: CurrentUser, session: SessionDep) -> BoardRunOut:
    board = _own_board(session, board_id, user.id)
    pipeline = session.get(Pipeline, pipeline_id)
    if pipeline is None or pipeline.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    run = session.get(BoardRun, board.id)
    if run is None:
        run = BoardRun(board_id=board.id, owner_id=user.id, pipeline_id=pipeline_id, state="stopped")
    else:
        run.pipeline_id = pipeline_id
        run.rotation_state = {}  # restart rotation on a new pipeline
        run.current_entry_id = None
    session.add(run)
    session.commit()
    session.refresh(run)
    return BoardRunOut.model_validate(run, from_attributes=True)


@router.get("/{board_id}/run", response_model=BoardRunOut)
def get_run(board_id: str, user: CurrentUser, session: SessionDep) -> BoardRunOut:
    _own_board(session, board_id, user.id)
    run = session.get(BoardRun, board_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no pipeline assigned")
    return BoardRunOut.model_validate(run, from_attributes=True)


@router.post("/{board_id}/start", response_model=BoardRunOut)
async def start(board_id: str, request: Request, user: CurrentUser, session: SessionDep) -> BoardRunOut:
    _own_board(session, board_id, user.id)
    run = session.get(BoardRun, board_id)
    if run is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "assign a pipeline first")
    if run.state != "running":  # start (re)begins from the top of the pipeline
        run.rotation_state = {}
        run.current_entry_id = None
    run.state = "running"
    session.add(run)
    session.commit()
    session.refresh(run)
    await request.app.state.manager.reconcile()
    return BoardRunOut.model_validate(run, from_attributes=True)


@router.post("/{board_id}/stop", response_model=BoardRunOut)
async def stop(board_id: str, request: Request, user: CurrentUser, session: SessionDep) -> BoardRunOut:
    _own_board(session, board_id, user.id)
    run = session.get(BoardRun, board_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no pipeline assigned")
    run.state = "stopped"
    session.add(run)
    session.commit()
    session.refresh(run)
    await request.app.state.manager.reconcile()
    return BoardRunOut.model_validate(run, from_attributes=True)
