"""filename

Revision ID: 0003
Revises: 0002
Create Date: 2016-03-21 00:08:17.476030

"""

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils
import whisker
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('config', schema=None) as batch_op:
        batch_op.alter_column('read_only',
               existing_type=mysql.TINYINT(display_width=1),
               type_=sa.Boolean(),
               existing_nullable=True)
        batch_op.alter_column('repeat_incomplete_trials',
               existing_type=mysql.TINYINT(display_width=1),
               type_=sa.Boolean(),
               existing_nullable=True)

    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.alter_column('from_server',
               existing_type=mysql.TINYINT(display_width=1),
               type_=sa.Boolean(),
               existing_nullable=True)

    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('filename', sa.Text(), nullable=True))

    with op.batch_alter_table('trial', schema=None) as batch_op:
        batch_op.alter_column('choice_offered',
               existing_type=mysql.TINYINT(display_width=1),
               type_=sa.Boolean(),
               existing_nullable=False)
        batch_op.alter_column('responded',
               existing_type=mysql.TINYINT(display_width=1),
               type_=sa.Boolean(),
               existing_nullable=False)
        batch_op.alter_column('response_correct',
               existing_type=mysql.TINYINT(display_width=1),
               type_=sa.Boolean(),
               existing_nullable=True)

    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('trial', schema=None) as batch_op:
        batch_op.alter_column('response_correct',
               existing_type=sa.Boolean(),
               type_=mysql.TINYINT(display_width=1),
               existing_nullable=True)
        batch_op.alter_column('responded',
               existing_type=sa.Boolean(),
               type_=mysql.TINYINT(display_width=1),
               existing_nullable=False)
        batch_op.alter_column('choice_offered',
               existing_type=sa.Boolean(),
               type_=mysql.TINYINT(display_width=1),
               existing_nullable=False)

    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.drop_column('filename')

    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.alter_column('from_server',
               existing_type=sa.Boolean(),
               type_=mysql.TINYINT(display_width=1),
               existing_nullable=True)

    with op.batch_alter_table('config', schema=None) as batch_op:
        batch_op.alter_column('repeat_incomplete_trials',
               existing_type=sa.Boolean(),
               type_=mysql.TINYINT(display_width=1),
               existing_nullable=True)
        batch_op.alter_column('read_only',
               existing_type=sa.Boolean(),
               type_=mysql.TINYINT(display_width=1),
               existing_nullable=True)

    ### end Alembic commands ###
