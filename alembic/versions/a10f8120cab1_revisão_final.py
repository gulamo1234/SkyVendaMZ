"""Revisão final

Revision ID: a10f8120cab1
Revises: 51d6ae244cff
Create Date: 2025-01-07 12:16:44.987634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a10f8120cab1'
down_revision: Union[str, None] = '51d6ae244cff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key(None, 'endereco_envio', 'pedido', ['pedidoID'], ['id'])
    op.alter_column('pedido', 'customer_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('pedido', 'produto_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.create_index(op.f('ix_pedido_id'), 'pedido', ['id'], unique=False)
    op.add_column('usuarios', sa.Column('referenciador_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'usuarios', 'usuarios', ['referenciador_id'], ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'usuarios', type_='foreignkey')
    op.drop_column('usuarios', 'referenciador_id')
    op.drop_index(op.f('ix_pedido_id'), table_name='pedido')
    op.alter_column('pedido', 'produto_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('pedido', 'customer_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_constraint(None, 'endereco_envio', type_='foreignkey')
    # ### end Alembic commands ###
