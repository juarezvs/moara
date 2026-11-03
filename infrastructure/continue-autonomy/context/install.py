"""Version-checked local Continue integration; preserve vendor bundle for rollback."""
from pathlib import Path
import datetime
import json
import shutil
import subprocess

source = Path(__file__).resolve().parent
extension = Path.home() / '.vscode/extensions/continue.continue-2.0.0-win32-x64'
metadata = json.loads((extension / 'package.json').read_text(encoding='utf-8'))
assert metadata['version'] == '2.0.0'
bundle = extension / 'out/extension.js'
original = bundle.read_text(encoding='utf-8')
marker = '// MOARA_AUTOMATIC_CONTEXT_V1'
if marker not in original:
    needle = '''  let didPrune = false;
  let msgsCopy = msgs.map((m12) => ({ ...m12 }));'''
    replacement = '''  // MOARA_AUTOMATIC_CONTEXT_V1: limit only the request, never the saved history.
  let moaraCompacted = false;
  if (modelName === "moara-code") {
    const packet = require("./moara-context.cjs").compactMessages(msgs, tools || [], {
      maxBytes: Math.min(12000, Math.max(6000, (knownContextLength || 6144) * 3 - 4500))
    });
    msgs = packet.messages;
    moaraCompacted = packet.compacted;
    if (moaraCompacted) console.info("Moara context compacted", packet.beforeBytes, packet.afterBytes);
  }
  let didPrune = moaraCompacted;
  let msgsCopy = msgs.map((m12) => ({ ...m12 }));'''
    assert original.count(needle) == 1, 'Installed bundle changed; refusing an ambiguous patch.'
    backup = bundle.with_name('extension.js.before-moara-context-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(bundle, backup)
    bundle.write_text(original.replace(needle, replacement), encoding='utf-8')
    try:
        subprocess.run(['node', '--check', str(bundle)], check=True, capture_output=True)
    except Exception:
        shutil.copy2(backup, bundle)
        raise
    print('Vendor bundle backup:', backup)
shutil.copy2(source / 'moara-context.cjs', extension / 'out/moara-context.cjs')
print('Automatic Moara context integration installed for Continue 2.0.0.')
