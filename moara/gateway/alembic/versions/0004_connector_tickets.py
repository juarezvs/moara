from pathlib import Path
from alembic import op
revision='0004_connector_tickets'
down_revision='0003_job_leases'
branch_labels=None
depends_on=None
def upgrade():op.execute((Path(__file__).resolve().parents[2]/'migrations/004_connector_tickets.sql').read_text())
def downgrade():raise RuntimeError('Use the reviewed backup/rollback procedure.')
