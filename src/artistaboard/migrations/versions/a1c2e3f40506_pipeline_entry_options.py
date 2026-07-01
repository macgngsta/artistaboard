"""pipeline entry options

Revision ID: a1c2e3f40506
Revises: 4bbfee5e9fd3
Create Date: 2026-06-30 21:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c2e3f40506'
down_revision: str | None = '4bbfee5e9fd3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('pipeline_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('options', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('pipeline_entries', schema=None) as batch_op:
        batch_op.drop_column('options')
