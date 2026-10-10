"""Add policies.stamp_duty and backfill Motor/Homeowners stamp duty

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-10-10 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("policies", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("stamp_duty", sa.Float(), nullable=False, server_default="0")
        )

    # Motor/Homeowners premium = rate_amount * 1.05 + levy, where stamp duty is 5% of
    # rate_amount. So stamp duty = (premium - levy) * 5 / 105. Manual products store
    # their own stamp duty percentage that is not recoverable here; those stay at 0
    # and must be corrected by hand.
    op.execute(
        """
        UPDATE policies
        SET stamp_duty = ROUND(CAST((premium_amount - levy) * 5.0 / 105.0 AS NUMERIC), 2)
        WHERE product_id IN (
            SELECT id FROM insurance_products
            WHERE name IN ('Motor Comprehensive', 'Third Party', 'Full Third Party', 'Homeowners')
        )
        AND premium_amount IS NOT NULL
        """
    )


def downgrade():
    with op.batch_alter_table("policies", schema=None) as batch_op:
        batch_op.drop_column("stamp_duty")

