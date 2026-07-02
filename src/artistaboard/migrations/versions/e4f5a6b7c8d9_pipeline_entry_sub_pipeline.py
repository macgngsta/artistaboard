"""pipeline_entry sub_pipeline_id (nested pipelines)

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5061728
Create Date: 2026-07-01

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5061728"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sub_pipeline_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pipeline_entries", schema=None) as batch_op:
        batch_op.drop_column("sub_pipeline_id")
