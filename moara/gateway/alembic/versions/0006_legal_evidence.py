from pathlib import Path
from alembic import op
revision='0006_legal_evidence'
down_revision='0005_platform'
branch_labels=None
depends_on=None

def upgrade():
    op.execute((Path(__file__).resolve().parents[2]/'migrations/006_legal_evidence.sql').read_text(encoding='utf-8'))

def downgrade():
    raise RuntimeError('Preserve evidence; use a reviewed archival procedure.')
