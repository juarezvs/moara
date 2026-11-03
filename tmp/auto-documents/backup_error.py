from pathlib import Path
import re
s=Path('/home/nutec/ai-server/secrets/moara-preservation-error.log').read_text()
known=['server closed the connection unexpectedly','the database system is starting up','No such file or directory','Connection refused','role','already exists','permission denied','unsupported version','out of memory']
print({'error_categories':[x for x in known if x in s]})
first=s.splitlines()[0] if s else ''
print(re.sub(r'"[^"]*"|\x27[^\x27]*\x27','[redacted]',first)[:240])
