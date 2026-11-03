from pathlib import Path
from alembic import op

revision = '0010_api_key_unlimited_rpm'
down_revision = '0009_chat_assistant_context'
branch_labels = None
depends_on = None


def upgrade():
    op.execute((Path(__file__).resolve().parents[2] / 'migrations/010_api_key_unlimited_rpm.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('Set unlimited keys to a positive quota before restoring the previous constraint.')
