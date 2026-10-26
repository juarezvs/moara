"""Bounded, offline parser subprocess. Never executes document instructions."""
import io
import resource
import sys
import zipfile

resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
raw = sys.stdin.buffer.read(1024**2 + 1)
if len(raw) > 1024**2:
    raise ValueError("file too large")
ext = sys.argv[1]
if ext == ".pdf":
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted or len(reader.pages) > 100:
        raise ValueError("encrypted or excessive page count")
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
elif ext == ".docx":
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > 1000 or sum(i.file_size for i in infos) > 10 * 1024**2:
            raise ValueError("archive limit")
    from docx import Document
    doc = Document(io.BytesIO(raw))
    text = "\n".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for r in t.rows for c in r.cells])
else:
    text = raw.decode("utf-8-sig")
if not text.strip() or len(text.encode("utf-8")) > 1024**2:
    raise ValueError("empty text, scanned PDF or excessive extracted text")
sys.stdout.write(text)
