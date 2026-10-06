"""Add levy column to policies

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("policies", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("levy", sa.Float(), nullable=False, server_default="0.0")
        )


def downgrade():
    with op.batch_alter_table("policies", schema=None) as batch_op:
        batch_op.drop_column("levy")
