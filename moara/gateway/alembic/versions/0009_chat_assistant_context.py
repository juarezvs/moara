from pathlib import Path
from alembic import op
revision='0009_chat_assistant_context'
down_revision='0008_official_assistants'
branch_labels=None
depends_on=None

def upgrade():
    op.execute((Path(__file__).resolve().parents[2]/'migrations/009_chat_assistant_context.sql').read_text(encoding='utf-8'))

def downgrade():
    raise RuntimeError('Preserve conversation context; no automatic destructive downgrade.')
