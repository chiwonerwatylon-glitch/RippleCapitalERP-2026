"""Mark remittances of fully paid policies as remitted to the insurer

Revision ID: b0c1d2e3f4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-10-10 15:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b0c1d2e3f4a5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade():
    # A policy whose premium is fully paid is passed on to the insurer automatically.
    op.execute(
        """
        UPDATE premium_remittances
        SET is_remitted_to_company = TRUE,
            date_remitted = COALESCE(date_remitted, NOW())
        WHERE policy_id IN (
            SELECT p.id
            FROM policies p
            JOIN (
                SELECT policy_id, SUM(amount) AS paid
                FROM premium_remittances
                GROUP BY policy_id
            ) t ON t.policy_id = p.id
            WHERE p.premium_amount > 0
              AND ROUND(CAST(p.premium_amount - t.paid AS NUMERIC), 2) <= 0
        )
        """
    )


def downgrade():
    pass
