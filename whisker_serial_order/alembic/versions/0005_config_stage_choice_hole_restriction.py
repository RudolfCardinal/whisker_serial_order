"""config_stage.choice_hole_restriction

Revision ID: 0005
Revises: 0004
Create Date: 2018-09-10 15:32:27.621830

"""

from alembic import op
import sqlalchemy as sa

from whisker_serial_order.models import ChoiceHoleRestrictionType

# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('config_stage', schema=None) as batch_op:
        batch_op.add_column(sa.Column('choice_hole_restriction', ChoiceHoleRestrictionType(length=255), nullable=True))  # noqa

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('config_stage', schema=None) as batch_op:
        batch_op.drop_column('choice_hole_restriction')

    # ### end Alembic commands ###
