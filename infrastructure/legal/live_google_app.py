"""Focused real-application regression for legal retrieval and evidence."""
import pathlib
root=pathlib.Path(__file__).resolve().parents[2]
source=(root/'infrastructure/legal/live_jurisprudence.py').read_text()
source=source.replace("root/'tmp/jurisprudence-stage.json'","root/'tmp/google-discovery-stage.json'")
source=source.replace("('jurisprudence-public.json' if public else 'jurisprudence-stage.json')","('google-app-public.json' if public else 'google-app-stage.json')")
source=source.replace("  for label,question,number in questions:","  for label,question,number in questions:\n   if label not in {'dialogue','traffic'}:continue")
exec(compile(source,'live_google_app','exec'),{'__file__':str(root/'infrastructure/legal/live_jurisprudence.py')})
