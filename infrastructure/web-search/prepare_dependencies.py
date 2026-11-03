"""Download only pinned binary wheels, with hash verification, for this Linux runtime."""
import pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[2];folder=root/'tmp/web-search-deps';folder.mkdir(exist_ok=True)
wheels=folder/'wheels';wheels.mkdir(exist_ok=True);wheels.chmod(0o777)
lock=root/'moara/legal_mcp/web-requirements.lock'
subprocess.run(['docker','run','--rm','--network','ai-server_download','-v',str(wheels)+':/wheels',
 '-v',str(lock)+':/requirements.lock:ro','--entrypoint','python','moara-core:pre-public-web-app-20261102',
 '-m','pip','download','--only-binary=:all:','--require-hashes','--dest','/wheels','-r','/requirements.lock'],check=True)
(folder/'requirements.lock').write_bytes(lock.read_bytes())
