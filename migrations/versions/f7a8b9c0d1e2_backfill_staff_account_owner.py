"""Link admin/agent users without an account owner to the owner account

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-10 12:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    # Staff created by seed/startup scripts were saved with NULL account_owner_id,
    # which scoped them to an empty account. Attach them to the owner account.
    op.execute(
        """
        UPDATE users
        SET account_owner_id = (
            SELECT MIN(o.id) FROM (SELECT id FROM users WHERE role = 'owner') AS o
        )
        WHERE role IN ('admin', 'agent') AND account_owner_id IS NULL
        """
    )


def downgrade():
    pass

