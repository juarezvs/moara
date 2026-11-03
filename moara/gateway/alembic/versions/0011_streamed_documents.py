from pathlib import Path
from alembic import op
revision='0011_streamed_documents'
down_revision='0010_api_key_unlimited_rpm'
branch_labels=None
depends_on=None
def upgrade():
 op.execute((Path(__file__).resolve().parents[2]/'migrations/011_streamed_documents.sql').read_text(encoding='utf8'))
def downgrade():
 raise RuntimeError('Streamed documents must be preserved before restoring the previous upload format.')
