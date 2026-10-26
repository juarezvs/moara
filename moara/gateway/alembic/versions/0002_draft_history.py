"""Preserve every saved draft instead of overwriting its previous contents."""
from pathlib import Path
from alembic import op
revision='0002_draft_history'
down_revision='0001_core'
branch_labels=None
depends_on=None

def upgrade():op.execute((Path(__file__).resolve().parents[2]/'migrations/002_draft_history.sql').read_text())
def downgrade():raise RuntimeError('Use the reviewed backup/rollback procedure.')
