import subprocess
code="""import shutil,importlib.util
print({x:bool(shutil.which(x)) for x in ['tesseract','pdftoppm']})
print({x:bool(importlib.util.find_spec(x)) for x in ['fitz','pypdf','pytesseract']})
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
print(subprocess.check_output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc',"SELECT display_name, context_length FROM moara.models m JOIN moara.model_bindings b ON b.model_id=m.id WHERE b.ready"],text=True))
