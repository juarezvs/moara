"""Add streaming storage without changing existing document bytes or ACLs."""
import pathlib,subprocess,json
root=pathlib.Path(__file__).resolve().parents[2]
def sql(value):
 return subprocess.check_output(['docker','exec','-i','ai-server-postgres-1','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','ai','-At'],input=value,text=True).strip()
current=sql('SELECT version_num FROM moara.alembic_version;')
if current=='0010_api_key_unlimited_rpm':
 backup=json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text());assert backup['verified'] is True
 before=sql("SELECT json_build_object('documents',count(*),'bytes',coalesce(sum(size_bytes),0)) FROM moara.document_blobs;")
 migration=(root/'moara/gateway/migrations/011_streamed_documents.sql').read_text()
 sql("BEGIN; SET LOCAL lock_timeout='5s'; SET LOCAL ROLE moara_migrator;\n"+migration+"\nUPDATE moara.alembic_version SET version_num='0011_streamed_documents' WHERE version_num='0010_api_key_unlimited_rpm';\nCOMMIT;")
 after=sql("SELECT json_build_object('documents',count(*),'bytes',coalesce(sum(size_bytes),0)) FROM moara.document_blobs;")
 assert before==after
 (root/'docs/runtime/document-upload-migration.json').write_text(json.dumps({'version':'0011_streamed_documents','existing_document_counts_and_sizes_preserved':True,'preservation_verified':True,'backup':backup['file']}))
elif current!='0011_streamed_documents':raise RuntimeError('Database changed; review migration order')
print(json.dumps({'migration':'0011_streamed_documents','ready':True}))
