"""add user password hash

Revision ID: b714aac59f7b
Revises: 81719300713d
Create Date: 2026-09-03 06:01:26.836471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b714aac59f7b'
down_revision: Union[str, Sequence[str], None] = '81719300713d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Autogenerate proposed a single NOT NULL add_column, which would fail on
    # any database that already has users: existing rows have no value for it.
    # The safe form is three steps.
    op.add_column(
        'users',
        sa.Column(
            'hashed_password',
            sqlmodel.sql.sqltypes.AutoString(length=128),
            nullable=True,
        ),
    )
    # Existing accounts get an unusable placeholder rather than a guessable
    # default. It is not a valid bcrypt hash, so verify_password can never
    # match it and those users must go through a password reset.
    op.execute("UPDATE users SET hashed_password = '!' WHERE hashed_password IS NULL")
    op.alter_column('users', 'hashed_password', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'hashed_password')


