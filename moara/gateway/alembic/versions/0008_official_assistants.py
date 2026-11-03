from pathlib import Path
from alembic import op
revision='0008_official_assistants'
down_revision='0007_legal_evidence_guard'
branch_labels=None
depends_on=None

def upgrade():
    op.execute((Path(__file__).resolve().parents[2]/'migrations/008_official_assistants.sql').read_text(encoding='utf-8'))

def downgrade():
    raise RuntimeError('Preserve assistant versions; use a reviewed archival procedure.')
