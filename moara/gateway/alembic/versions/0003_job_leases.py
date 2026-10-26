from pathlib import Path
from alembic import op
revision='0003_job_leases'
down_revision='0002_draft_history'
branch_labels=None
depends_on=None
def upgrade():op.execute((Path(__file__).resolve().parents[2]/'migrations/003_job_leases.sql').read_text())
def downgrade():raise RuntimeError('Use the reviewed backup/rollback procedure.')
