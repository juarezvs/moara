from pathlib import Path
from alembic import op
revision='0005_platform'
down_revision='0004_connector_tickets'
branch_labels=None
depends_on=None
def upgrade():op.execute((Path(__file__).resolve().parents[2]/'migrations/005_platform.sql').read_text(encoding='utf-8'))
def downgrade():raise RuntimeError('Use the reviewed preservation procedure; no automatic destructive downgrade.')
