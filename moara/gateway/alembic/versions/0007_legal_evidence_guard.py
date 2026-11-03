from pathlib import Path
from alembic import op
revision='0007_legal_evidence_guard'
down_revision='0006_legal_evidence'
branch_labels=None
depends_on=None

def upgrade():
    op.execute((Path(__file__).resolve().parents[2]/'migrations/007_legal_evidence_guard.sql').read_text(encoding='utf-8'))

def downgrade():
    raise RuntimeError('Preserve evidence; no automatic removal of audit safeguards.')
