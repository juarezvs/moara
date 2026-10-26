import base64
import json
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment, select_autoescape
from PIL import Image, ImageDraw

import browser
import core

TEMPLATE = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>{{ title }}</title><style>
@page{size:A4}*{box-sizing:border-box}body{font:11px 'DejaVu Sans',Arial,sans-serif;color:#172b45;line-height:1.55}h1{font-size:30px;letter-spacing:-1px}h2{font-size:20px;color:#194b82}h3{font-size:14px}p{color:#44566d}.page{break-after:page}.page:last-child{break-after:auto}.cover{padding-top:90px;min-height:850px}.line{height:5px;background:#2563eb;width:65px;margin:25px 0}.kicker{font-size:10px;letter-spacing:2px;color:#2563eb;text-transform:uppercase}.meta{margin-top:55px;border-top:1px solid #dbe3ed;padding-top:20px}.toc a{display:flex;justify-content:space-between;color:#25436b;text-decoration:none;border-bottom:1px dotted #cbd5e1;padding:12px 0}.status{background:#e5f4f0;color:#15745c;padding:5px 10px;border-radius:4px;font-size:9px;display:inline-block}img{width:auto;max-width:100%;max-height:350px;display:block;object-fit:contain;border:1px solid #d7e0ed;border-radius:6px;margin:12px 0}small{color:#687b94;font-size:8px}.note{padding:12px;background:#f1f5fa;border-left:3px solid #2563eb}.procedure{page-break-inside:avoid}li{margin:7px 0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #dbe3ed;padding:8px;text-align:left}
</style><body><section class="page cover"><div class="kicker">Moara Studio · Manual de utilização</div><div class="line"></div><h1>{{ title }}</h1><p>{{ system }}</p><p>{{ audience }}</p><div class="meta"><p>Versão {{ version }} · {{ date }}</p><p>Escopo: {{ scope }}</p><span class="status">Baseado em navegação real, somente leitura</span></div></section>
<section class="page toc"><h2>Índice</h2><a href="#intro">Introdução <span data-page-for="intro">3</span></a>{% for item in procedures %}<a href="#p{{ loop.index }}">{{ loop.index }}. {{ item.title }} <span data-page-for="p{{ loop.index }}">{{ loop.index + 3 }}</span></a>{% endfor %}<a href="#annex">Evidências e limitações <span data-page-for="annex">{{ procedures|length + 4 }}</span></a></section>
<section class="page" id="intro"><h2>Introdução</h2><p>Este manual documenta páginas efetivamente acessadas no sistema {{ system }}. Não certifica regras de negócio nem fluxos que dependam de gravação.</p><h3>Pré-requisitos</h3><ol><li>Ter acesso ao ambiente autorizado e ao perfil de teste correspondente.</li><li>Utilizar navegador atualizado e autenticar-se pelo procedimento da instituição.</li><li>Conferir a versão do ambiente antes de seguir as instruções.</li></ol><h3>Como ler as evidências</h3><p>Os destaques numerados correspondem a elementos observados no DOM. Campos sensíveis foram ocultados. A navegação registrada não aprovou nem alterou dados.</p><div class="note">Solicitações de alteração, envio, aprovação e exclusão permanecem pendentes de validação específica.</div></section>
{% for item in procedures %}<section class="page procedure" id="p{{ loop.index }}"><div class="kicker">Procedimento {{ loop.index }}</div><h2>{{ item.title }}</h2><span class="status">Verificado por navegação</span><h3>Objetivo</h3><p>Consultar a página {{ item.title }} no ambiente autorizado.</p><h3>Passo a passo</h3><ol><li>{{ item.action }}.</li><li>Confira o título e os elementos identificados na captura.</li>{% for label in item.labels %}<li>Localize o elemento “{{ label }}”, identificado na tela.</li>{% endfor %}</ol><img src="data:image/png;base64,{{ item.image }}"><small>Origem: {{ item.url }} · {{ item.time }} · viewport {{ item.viewport }} · execução {{ job_id }}</small><h3>Resultado observado</h3><p>{{ item.observed }}</p><p class="note">A observação confirma a tela e seus rótulos; operações de gravação não foram executadas.</p>{% if item.review %}<h3>Revisão humana desta seção</h3><p>{{ item.review }}</p>{% endif %}</section>{% endfor %}
<section id="annex"><h2>Evidências e limitações</h2><p>Origem: exploração {{ source_job }}, realizada em {{ date }}.</p><table><tr><th>Página</th><th>Estado</th></tr>{% for item in procedures %}<tr><td>{{ item.title }}</td><td>Verificado por navegação</td></tr>{% endfor %}<tr><td>Operações com efeito externo</td><td>Pendente de validação</td></tr></table><h3>Glossário</h3><p>Perfil de teste: identidade autorizada para a execução. Evidência: captura e metadados coletados na navegação. Somente leitura: requisições de alteração bloqueadas.</p><h3>Revisão</h3><p>{{ review_note }}</p></section></body></html>'''

async def run(job, progress):
    data = job['input']
    path = core.job_directory(job['id'])
    if data.get('source_job'):
        source = await core.sql('SELECT * FROM studio_jobs WHERE id=%s AND owner=%s', (data['source_job'], job['owner']), one=True)
        if not source or source['status'] != 'completed' or source['kind'] not in ('browser', 'manuals'):
            raise RuntimeError('Escolha uma exploração concluída da sua conta')
        evidence = source['result']['metadata']['evidence']
        system_name = source['result']['metadata']['system']
        for item in evidence:
            shutil.copyfile(core.file_path(source['id'], item['file']), path / item['file'])
    else:
        explored = await browser.explore(job, progress, max_pages=min(data.get('max_pages', 5), 10))
        evidence, system_name = explored['evidence'], explored['system']
    evidence_job = str(source['result']['metadata'].get('source_job') or source['id']) if data.get('source_job') else str(job['id'])
    await progress('Relacionando instruções às evidências reais', 70)
    procedures = []
    for index, item in enumerate(evidence):
        image = Image.open(path / item['file']).convert('RGB')
        draw = ImageDraw.Draw(image)
        labeled = []
        for element in item['elements']:
            rect = element['rect']
            if element['tag'] in ('a', 'button', 'label') and element['text'] and rect['width'] > 3 and 0 <= rect['y'] < 850:
                labeled.append(element['text'])
                number = len(labeled)
                x, y = max(1, rect['x']), max(1, rect['y'])
                draw.rectangle((x, y, x + rect['width'], y + rect['height']), outline='#2563eb', width=2)
                draw.ellipse((x, y, x + 22, y + 22), fill='#2563eb')
                draw.text((x + 6, y + 4), str(number), fill='white')
                if number == 4:
                    break
        annotated = f'annotated-{index+1:03}.png'
        image.save(path / annotated)
        review = data.get('section_reviews', {}).get(str(index + 1), '')[:1500]
        procedures.append({'title': item['title'], 'action': item['action'], 'labels': labeled, 'review': review,
            'url': item['url'], 'viewport': str(item['viewport']),
            'time': datetime.fromtimestamp(item['timestamp'], ZoneInfo('America/Manaus')).strftime('%d/%m/%Y %H:%M'),
            'observed': item['text'][:320], 'image': base64.b64encode((path / annotated).read_bytes()).decode()})
    # AI summary is grounded in the collected DOM; procedure labels remain deterministic.
    summary = await core.language('Resuma em português, em um parágrafo, o escopo realmente observado nestas telas. Não crie regras nem telas.\n' +
        json.dumps([{'title': p['title'], 'text': p['observed']} for p in procedures], ensure_ascii=False), tokens=260)
    values = {'title': data.get('title') or 'Manual de utilização · ' + system_name, 'system': system_name,
        'audience': data.get('audience', 'Usuários autorizados'), 'scope': data.get('prompt', 'Páginas acessíveis em leitura'),
        'version': '1.0', 'date': datetime.now(ZoneInfo('America/Manaus')).strftime('%d/%m/%Y %H:%M'),
        'procedures': procedures, 'job_id': str(job['id']), 'source_job': evidence_job, 'review_note': data.get('review_note') or summary}
    output = Environment(autoescape=select_autoescape(default=True)).from_string(TEMPLATE).render(**values)
    (path / 'manual.html').write_text(output, encoding='utf-8')
    (path / 'manual-source.json').write_text(json.dumps({'title': values['title'], 'summary': summary,
        'system': system_name, 'source_job': evidence_job, 'evidence': evidence}, ensure_ascii=False, indent=2), encoding='utf-8')
    await progress('Renderizando PDF A4 no Chromium', 88)
    await core.renderer('/pdf', {'job_id': str(job['id']), 'html': output})
    return {'summary': values['title'], 'artifacts': [p.name for p in path.iterdir() if p.is_file()],
        'metadata': {'system': system_name, 'source_job': evidence_job, 'evidence': evidence, 'procedures': len(procedures),
            'verified_by_navigation': True, 'review_note': values['review_note']}}
