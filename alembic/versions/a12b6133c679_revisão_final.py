"""Revisão final

Revision ID: a12b6133c679
Revises: 1a2dfac501e8
Create Date: 2025-01-10 11:22:49.178611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a12b6133c679'
down_revision: Union[str, None] = '1a2dfac501e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('anuncio', sa.Column('ativo', sa.Boolean(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('anuncio', 'ativo')
    # ### end Alembic commands ###
