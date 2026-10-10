"""Add users.account_owner_id and clients.user_id

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-07 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("account_owner_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_account_owner_id_users", "users", ["account_owner_id"], ["id"]
        )

    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_clients_user_id_users", "users", ["user_id"], ["id"]
        )
        batch_op.create_unique_constraint("uq_clients_user_id", ["user_id"])

    # Data step: attach existing admin/agent users to the earliest owner account.
    op.execute(
        """
        UPDATE users
        SET account_owner_id = (
            SELECT MIN(o.id) FROM (SELECT id FROM users WHERE role = 'owner') AS o
        )
        WHERE role IN ('admin', 'agent')
        """
    )


def downgrade():
    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.drop_constraint("uq_clients_user_id", type_="unique")
        batch_op.drop_constraint("fk_clients_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("fk_users_account_owner_id_users", type_="foreignkey")
        batch_op.drop_column("account_owner_id")
