"""Own Moara domain only. Existing legacy and connector schemas are preserved."""
from pathlib import Path
from alembic import op

revision='0001_core'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    script=Path(__file__).resolve().parents[2]/'migrations/001_core.sql'
    op.execute(script.read_text())

def downgrade():
    raise RuntimeError('Destructive automatic downgrade is disabled; use the reviewed preservation and rollback procedure.')
