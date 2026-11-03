"""Publish only the institution's public TLS trust anchor for IDE clients."""
import pathlib,ssl,urllib.request,hashlib
from cryptography import x509
from cryptography.hazmat.primitives import hashes
root=pathlib.Path(__file__).resolve().parents[2]
source=root/'docs/runtime/moara-domain-root-ca.crt';raw=source.read_bytes()
assert b'PRIVATE KEY' not in raw
cert=x509.load_pem_x509_certificate(raw)
assert cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
ctx=ssl.create_default_context();ctx.load_verify_locations(cafile=str(source))
with urllib.request.urlopen('https://moara.am.trf1.gov.br/moara/api/v1/health',context=ctx,timeout=15) as r:assert r.status==200
target=root/'moara/web/public/integrations/moara-domain-root-ca.crt';target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
print('PUBLIC_CA_VERIFIED_AND_PREPARED '+cert.fingerprint(hashes.SHA256()).hex())
