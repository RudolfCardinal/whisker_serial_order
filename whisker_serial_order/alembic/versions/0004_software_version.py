"""software_version

Revision ID: 0004
Revises: 0003
Create Date: 2016-03-22 20:46:12.331294

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    # commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('software_version', sa.String(length=50), nullable=True))

        # end Alembic commands ###


def downgrade():
    # commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.drop_column('software_version')

        # end Alembic commands ###
