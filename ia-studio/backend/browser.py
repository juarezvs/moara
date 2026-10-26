import base64
import json
import shutil
import uuid

from fastapi import HTTPException
from psycopg.types.json import Jsonb

import core

async def get_system(identifier, owner, admin=False):
    if identifier == 'demo':
        row = await core.sql("SELECT * FROM studio_systems WHERE name='Demonstração Moara Studio' LIMIT 1", one=True)
    else:
        try:
            uuid.UUID(identifier)
        except ValueError:
            raise HTTPException(404, 'Sistema não cadastrado')
        row = await core.sql('SELECT * FROM studio_systems WHERE id=%s', (identifier,), one=True)
    if not row:
        raise HTTPException(404, 'Cadastre um sistema autorizado antes da exploração')
    settings = row['settings']
    if not admin and row['owner'] != owner and owner not in settings.get('allowed_owners', []) and not settings.get('shared_demo'):
        raise HTTPException(403, 'Sistema não autorizado para esta conta')
    return row

async def create_session(system, owner, mode='observe'):
    settings = {k: system['settings'][k] for k in ('base_url', 'origins', 'hosts', 'paths', 'masks', 'allowed_fill')}
    if system.get('credentials'):
        settings['login'] = json.loads(core.CRYPTO.decrypt(bytes(system['credentials'])))
    created = await core.renderer('/sessions', settings)
    await core.sql('INSERT INTO studio_sessions(id,owner,system_id,mode,status) VALUES (%s,%s,%s,%s,%s)',
        (created['session_id'], owner, system['id'], mode, 'active'))
    return created

async def owned_session(sid, owner):
    try:
        uuid.UUID(sid)
    except ValueError:
        raise HTTPException(404, 'Sessão não encontrada')
    session = await core.sql('SELECT * FROM studio_sessions WHERE id=%s AND owner=%s', (sid, owner), one=True)
    if not session:
        raise HTTPException(404, 'Sessão não encontrada')
    return session

async def record(sid, owner, screenshot, action='Captura autorizada'):
    session = await owned_session(sid, owner)
    evidence = session['evidence']
    filename = f'evidence-{len(evidence)+1:03}.png'
    raw = base64.b64decode(screenshot.pop('screenshot'))
    (core.job_directory(sid) / filename).write_bytes(raw)
    item = {**screenshot, 'file': filename, 'action': action, 'index': len(evidence) + 1}
    evidence.append(item)
    await core.sql('UPDATE studio_sessions SET evidence=%s WHERE id=%s', (Jsonb(evidence[-60:]), sid))
    return item

async def explore(job, progress, *, max_pages=None):
    data = job['input']
    system = await get_system(data.get('system_id', 'demo'), job['owner'], data.get('_admin', False))
    created = await create_session(system, job['owner'], 'explore')
    sid = created['session_id']
    visited = set()
    queue = [(system['settings']['base_url'], 0, 'Abrir o sistema autorizado')]
    evidence = []
    maximum = max_pages or min(data.get('max_pages', 6), 12)
    try:
        while queue and len(evidence) < maximum:
            url, depth, label = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            await progress('Navegação somente leitura: ' + str(len(evidence) + 1) + '/' + str(maximum),
                15 + int(50 * len(evidence) / maximum))
            snapshot = await core.renderer('/sessions/' + sid + '/actions', {'action': 'goto', 'target': url})
            item = await record(sid, job['owner'], snapshot, label)
            target_name = f'screen-{len(evidence)+1:03}.png'
            shutil.copyfile(core.job_directory(sid) / item['file'], core.job_directory(job['id']) / target_name)
            item['file'] = target_name
            evidence.append(item)
            if depth < min(data.get('depth', 2), 3):
                for element in item['elements']:
                    href = element.get('href')
                    if href and href not in visited and len(queue) < 30:
                        queue.append((href, depth + 1, 'Selecionar o menu ' + (element['text'] or 'observado')))
        if not evidence:
            raise RuntimeError('Nenhuma página autorizada pôde ser observada')
        result = {'system': system['name'], 'system_id': str(system['id']), 'evidence': evidence,
            'read_only': True, 'verified_pages': len(evidence), 'session_id': sid,
            'limitations': ['Nenhum fluxo de gravação, aprovação ou exclusão foi executado.']}
        path = core.job_directory(job['id'])
        (path / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        await core.renderer('/sessions/' + sid, method='DELETE')
        await core.sql("UPDATE studio_sessions SET status='closed' WHERE id=%s", (sid,))

async def run(job, progress):
    result = await explore(job, progress)
    return {'summary': f"{result['verified_pages']} páginas observadas em leitura", 'metadata': result,
        'artifacts': ['evidence.json', *[e['file'] for e in result['evidence']]]}
