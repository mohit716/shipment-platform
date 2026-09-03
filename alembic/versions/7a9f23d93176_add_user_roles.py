"""add user roles

Revision ID: 7a9f23d93176
Revises: b714aac59f7b
Create Date: 2026-09-03 06:23:16.332304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7a9f23d93176'
down_revision: Union[str, Sequence[str], None] = 'b714aac59f7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # CREATE TYPE has to be issued explicitly. create_table emits it for any
    # enum column it sees, but add_column does not, so autogenerate's version
    # of this migration failed with "type userrole does not exist".
    role_enum = sa.Enum('customer', 'staff', name='userrole')
    role_enum.create(op.get_bind(), checkfirst=True)

    # server_default is what makes this safe on a table that already has rows:
    # without it, adding a NOT NULL column to existing users fails. Existing
    # accounts become customers, which is the safe direction to default a
    # permission.
    op.add_column(
        'users',
        sa.Column(
            'role',
            # create_type=False: the type was just created above, and letting
            # this try again would raise DuplicateObject.
            postgresql.ENUM('customer', 'staff', name='userrole', create_type=False),
            nullable=False,
            server_default='customer',
        ),
    )
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_column('users', 'role')
    # Dropping the column leaves the enum type behind in PostgreSQL, and the
    # next upgrade would then fail with "type userrole already exists".
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
