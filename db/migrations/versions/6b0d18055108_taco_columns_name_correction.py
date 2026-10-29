"""taco_columns_name_correction
Corrigir grafia das colunas nutricionais fosforo, cinzas, umidade e vitamina C em ingles.

Revision ID: 6b0d18055108
Revises: 129f325b8c1f
Create Date: 2026-10-29 17:01:10.409874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b0d18055108'
down_revision: Union[str, Sequence[str], None] = '129f325b8c1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('taco', 'phosphoru', new_column_name='phosphorus')
    op.alter_column('taco', 'ashe', new_column_name='ash')
    op.alter_column('taco', 'humidity', new_column_name='moisture')
    op.alter_column('taco', 'c_vitamin', new_column_name='vitamin_c')


def downgrade() -> None:
    op.alter_column('taco', 'vitamin_c', new_column_name='c_vitamin')
    op.alter_column('taco', 'moisture', new_column_name='humidity')
    op.alter_column('taco', 'ash', new_column_name='ashe')
    op.alter_column('taco', 'phosphorus', new_column_name='phosphoru')
