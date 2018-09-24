"""config_stage.serial_pos_restriction

Revision ID: 0007
Revises: 0006
Create Date: 2018-09-24 22:12:43.730490

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

import whisker_serial_order.models


# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('config_stage', schema=None) as batch_op:
        batch_op.add_column(sa.Column('serial_pos_restriction', whisker_serial_order.models.SerialPosRestrictionType(length=255), nullable=True))  # noqa
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('config_stage', schema=None) as batch_op:
        batch_op.drop_column('serial_pos_restriction')
    # ### end Alembic commands ###
