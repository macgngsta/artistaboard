"""board_run last_frame_hash

Revision ID: d3e4f5061728
Revises: c2d3e4f50617
Create Date: 2026-06-30 21:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'd3e4f5061728'
down_revision: str | None = 'c2d3e4f50617'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('board_runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_frame_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('board_runs', schema=None) as batch_op:
        batch_op.drop_column('last_frame_hash')
