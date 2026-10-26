import html
import json
import re
import zipfile
from pathlib import Path

from jinja2 import Environment, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

import core

class KPI(BaseModel):
    label: str = Field(max_length=60)
    value: str = Field(max_length=30)
    note: str = Field(default='Dados ilustrativos', max_length=90)

class DesignSpec(BaseModel):
    model_config = ConfigDict(extra='ignore')
    title: str = Field(max_length=100)
    subtitle: str = Field(default='', max_length=220)
    navigation: list[str] = Field(min_length=2, max_length=8)
    kpis: list[KPI] = Field(min_length=3, max_length=6)
    columns: list[str] = Field(min_length=2, max_length=6)
    rows: list[list[str]] = Field(min_length=2, max_length=8)
    section_title: str = Field(default='Visão operacional', max_length=100)

STYLE = '''
:root{--accent:{{ accent }};--bg:{{ bg }};--surface:{{ surface }};--ink:{{ ink }};--muted:{{ muted }}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px 'DejaVu Sans',Arial,sans-serif}
.app{display:grid;grid-template-columns:232px 1fr;min-height:100vh}aside{background:#10213a;color:#c7d5e7;padding:32px 20px}
.brand{font-size:20px;font-weight:800;color:white;margin-bottom:42px}.mark{display:inline-grid;place-items:center;background:var(--accent);border-radius:9px;width:32px;height:32px;margin-right:10px;color:white}
aside a{display:block;color:inherit;text-decoration:none;padding:13px 15px;border-radius:8px;margin:6px 0}aside a:first-of-type{background:#ffffff16;color:#fff;border-left:3px solid var(--accent)}
main{min-width:0;padding:32px 40px}.top{display:flex;justify-content:space-between;align-items:center;padding-bottom:24px;border-bottom:1px solid #94a3b830;font-size:12px;color:var(--muted)}
.avatar{background:#dce9fa;color:#21436d;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;font-weight:700}
.hero{display:flex;justify-content:space-between;gap:18px;align-items:center;margin:32px 0}.eyebrow{text-transform:uppercase;letter-spacing:2px;font-size:10px;font-weight:700;color:var(--accent)}
h1{font-size:30px;letter-spacing:-1px;margin:9px 0}p{color:var(--muted);line-height:1.6}button{border:0;background:var(--accent);padding:13px 18px;border-radius:7px;color:white;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat({{ count }},minmax(0,1fr));gap:18px}.card,.panel{background:var(--surface);border:1px solid #94a3b82c;border-radius:11px;padding:22px}.card label{color:var(--muted);font-size:12px}.value{font-size:28px;font-weight:750;margin:15px 0 10px}.note{font-size:10px;color:var(--muted)}
.grid{display:grid;grid-template-columns:1.6fr 1fr;gap:20px;margin:24px 0}h2{font-size:15px;margin:0 0 24px}.bars{display:flex;gap:17px;height:155px;align-items:end;border-bottom:1px solid #94a3b84a;padding:0 12px}.bar{flex:1;border-radius:5px 5px 0 0;background:var(--accent);min-height:10px;opacity:.85}.labels{display:flex;justify-content:space-around;font-size:10px;color:var(--muted);padding:10px}
.activity{display:flex;gap:13px;border-bottom:1px solid #94a3b825;padding:14px 0;font-size:12px}.dot{width:9px;height:9px;flex-shrink:0;background:var(--accent);border-radius:50%;margin-top:4px}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th,td{text-align:left;padding:15px 13px;border-bottom:1px solid #94a3b82c}th{background:var(--bg);color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.badge{font-size:10px;padding:5px 9px;background:#14b8a61a;color:#0d9488;border-radius:20px}.footer{font-size:10px;color:var(--muted);margin-top:22px}
@media(max-width:1000px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.grid{grid-template-columns:1fr}.app{grid-template-columns:190px 1fr}main{padding:25px}}
@media(max-width:620px){.app{display:block}aside{padding:15px 18px}.brand{margin:0;font-size:17px}aside nav{display:flex;overflow:auto;margin-top:12px}aside a{font-size:11px;white-space:nowrap;padding:8px 12px;margin:0}.mark{width:27px;height:27px}main{padding:22px 17px}.hero{display:block;margin:24px 0}h1{font-size:25px}.hero button{margin-top:10px}.kpis{gap:10px}.card{padding:16px}.value{font-size:25px}.panel{padding:17px}.top{font-size:10px}.grid{gap:14px}.bars{height:120px;gap:10px}.table-wrap{max-width:100%}}
'''

TEMPLATE = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ spec.title }}</title>
<style>{{ css | safe }}</style><body><div class="app"><aside><div class="brand"><span class="mark">IA</span>{{ brand }}</div><nav>{% for n in spec.navigation %}<a href="#visao">{{ n }}</a>{% endfor %}</nav></aside>
<main id="visao"><div class="top"><span>Workspace / {{ spec.title }}</span><span class="avatar">NT</span></div>
<header class="hero"><div><div class="eyebrow">{{ application }}</div><h1>{{ spec.title }}</h1><p>{{ spec.subtitle }}</p></div><button type="button">Visão do período</button></header>
<section class="kpis">{% for kpi in spec.kpis %}<div class="card"><label>{{ kpi.label }}</label><div class="value">{{ kpi.value }}</div><div class="note">{{ kpi.note }}</div></div>{% endfor %}</section>
<div class="grid"><section class="panel"><h2>{{ spec.section_title }}</h2><div class="bars">{% for h in [42,65,52,78,59,91,74] %}<div class="bar" style="height:{{ h }}%"></div>{% endfor %}</div><div class="labels">{% for d in ['SEG','TER','QUA','QUI','SEX','SAB','DOM'] %}<span>{{ d }}</span>{% endfor %}</div><div class="note">Distribuição ilustrativa · substitua pelos dados da aplicação</div></section>
<section class="panel"><h2>Acompanhamento</h2>{% for kpi in spec.kpis[:3] %}<div class="activity"><span class="dot"></span><div>{{ kpi.label }}<p style="margin:5px 0">{{ kpi.note }}</p></div></div>{% endfor %}</section></div>
<section class="panel"><h2>Registros do período <span class="badge">Demonstração</span></h2><div class="table-wrap"><table><thead><tr>{% for col in spec.columns %}<th>{{ col }}</th>{% endfor %}</tr></thead><tbody>{% for row in spec.rows %}<tr>{% for col in spec.columns %}<td>{{ row[loop.index0] if loop.index0 < row|length else '—' }}</td>{% endfor %}</tr>{% endfor %}</tbody></table></div></section><footer class="footer">Moara Studio · Interface gerada com dados ilustrativos · {{ framework }}</footer></main></div></body></html>'''

ENV = Environment(autoescape=select_autoescape(default=True))

async def generate(job, progress, reference_note=''):
    data = job['input']
    path = core.job_directory(job['id'])
    await progress('Interpretando a interface com o modelo local', 12)
    schema = json.dumps(DesignSpec.model_json_schema(), ensure_ascii=False)
    prompt = ('Crie uma especificação JSON de interface para a solicitação abaixo. '
        'Dados numéricos são somente exemplos: identifique-os como ilustrativos. '
        'Escreva em português, use títulos curtos. Não inclua código nem Markdown. '
        'Schema: ' + schema + '\nSolicitação: ' + data['prompt'] +
        '\nPreferências: ' + json.dumps({k: v for k, v in data.items() if k not in ('prompt', 'reference')}, ensure_ascii=False) +
        '\nReferência visual observada: ' + reference_note)
    source = await core.language(prompt, json_mode=True, tokens=1400, model=data.get('model', 'general'))
    try:
        specification = DesignSpec.model_validate_json(source)
    except ValueError:
        # A schema correction is a bounded second attempt, not a fabricated success.
        corrected = await core.language('Corrija este JSON para cumprir o schema, retorne só JSON.\nSchema:' + schema + '\nJSON:' + source[:18000], json_mode=True, tokens=1400)
        specification = DesignSpec.model_validate_json(corrected)
    (path / 'specification.json').write_text(specification.model_dump_json(indent=2), encoding='utf-8')
    await progress('Gerando código responsivo', 45)
    accent = data.get('color', '#2563eb')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        accent = '#2563eb'
    dark = data.get('theme') == 'dark'
    colors = {'accent': accent, 'bg': '#0b1220' if dark else '#f3f6fb',
        'surface': '#152036' if dark else '#ffffff', 'ink': '#e3ebf8' if dark else '#16253b',
        'muted': '#99abc4' if dark else '#738198', 'count': min(4, len(specification.kpis))}
    css = ENV.from_string(STYLE).render(**colors)
    rendered = ENV.from_string(TEMPLATE).render(spec=specification, css=css,
        brand=data.get('brand', 'Moara AI'), application=data.get('application', 'Dashboard'), framework=data.get('framework', 'html'))
    (path / 'dashboard.html').write_text(rendered, encoding='utf-8')
    (path / 'styles.css').write_text(css, encoding='utf-8')
    if data.get('framework') in ('react', 'angular'):
        # Typed, escaped markup generated from the validated spec; no generated code runs on the host.
        if data['framework'] == 'react':
            tsx = 'import React from "react";\nimport "./styles.css";\nconst spec = ' + specification.model_dump_json() + ';\n'
            tsx += '''export default function Dashboard(){return <div className="app"><aside><div className="brand"><span className="mark">IA</span>Workspace</div><nav>{spec.navigation.map(n=><a key={n} href="#visao">{n}</a>)}</nav></aside><main id="visao"><div className="top">Workspace / {spec.title}</div><header className="hero"><div><div className="eyebrow">Painel de gestão</div><h1>{spec.title}</h1><p>{spec.subtitle}</p></div><button type="button">Visão do período</button></header><section className="kpis">{spec.kpis.map(k=><article className="card" key={k.label}><label>{k.label}</label><div className="value">{k.value}</div><div className="note">{k.note}</div></article>)}</section><div className="grid"><section className="panel"><h2>{spec.section_title}</h2><div className="bars">{[42,65,52,78,59,91,74].map((h,i)=><div key={i} className="bar" style={{height:h+"%"}} />)}</div><p className="note">Distribuição ilustrativa</p></section><section className="panel"><h2>Acompanhamento</h2>{spec.kpis.slice(0,3).map(k=><div key={k.label} className="activity"><span className="dot"/><div>{k.label}<p>{k.note}</p></div></div>)}</section></div><section className="panel"><h2>Registros do período</h2><div className="table-wrap"><table><thead><tr>{spec.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{spec.rows.map((r,i)=><tr key={i}>{spec.columns.map((c,j)=><td key={c}>{r[j]??"—"}</td>)}</tr>)}</tbody></table></div></section><footer className="footer">Moara Studio · Dados ilustrativos</footer></main></div>}'''
            (path / 'Dashboard.tsx').write_text(tsx, encoding='utf-8')
            (path / 'main.tsx').write_text('import React from "react";import{createRoot}from"react-dom/client";import Dashboard from"./Dashboard";createRoot(document.getElementById("root")!).render(<Dashboard/>);', encoding='utf-8')
            (path / 'index.html').write_text('<html><meta charset="utf-8"><div id="root"></div><script type="module" src="/main.tsx"></script></html>', encoding='utf-8')
            (path / 'package.json').write_text(json.dumps({'name': 'ia-studio-dashboard', 'private': True, 'version': '1.0.0', 'type': 'module',
                'scripts': {'dev': 'vite --host 127.0.0.1', 'build': 'vite build'},
                'dependencies': {'react': '19.3.1', 'react-dom': '19.3.1'},
                'devDependencies': {'typescript': '7.0.2', 'vite': '8.3.4', '@types/react': '19.3.0', '@types/react-dom': '19.3.0'}}, indent=2))
            (path / 'tsconfig.json').write_text(json.dumps({'compilerOptions': {'target': 'ES2022', 'module': 'ESNext', 'moduleResolution': 'bundler', 'jsx': 'react-jsx', 'strict': True, 'esModuleInterop': True, 'skipLibCheck': True}, 'include': ['*.tsx']}, indent=2))
        else:
            (path / 'dashboard.component.html').write_text(rendered.split('<body>',1)[1].split('</body>',1)[0], encoding='utf-8')
            (path / 'dashboard.component.ts').write_text('import{Component,ViewEncapsulation}from"@angular/core";@Component({selector:"app-dashboard",standalone:true,encapsulation:ViewEncapsulation.None,templateUrl:"./dashboard.component.html",styleUrl:"./styles.css"})export class DashboardComponent{}', encoding='utf-8')
    await progress('Renderizando desktop e mobile no Chromium isolado', 65)
    dimensions = {'width': data.get('width', 1440), 'height': data.get('height', 1000)}
    evidence = await core.renderer('/react' if data.get('framework') == 'react' else '/render',
        {'job_id': str(job['id']), **dimensions, **({} if data.get('framework') == 'react' else {'html': rendered})})
    if evidence['errors']:
        raise RuntimeError('A renderização apresentou erro: ' + str(evidence['errors']))
    if evidence['mobile']['scroll'] > evidence['mobile']['width'] + 2:
        raise RuntimeError('A versão mobile excedeu a largura da tela')
    await progress('Empacotando código e evidências', 90)
    metadata = {'generator_model': data.get('model', 'general'), 'render': evidence,
        'refines_job': data.get('parent_job'), 'framework': data.get('framework', 'html'),
        'data_classification': 'illustrative', 'react_implementation': 'typed JSX component' if data.get('framework') == 'react' else None}
    (path / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    (path / 'README.txt').write_text('Dashboard gerado pelo Moara Studio. Os dados são ilustrativos.\nAbra dashboard.html para usar o layout sem dependências externas.\nQuando selecionado React, execute npm install e npm run dev no ambiente de desenvolvimento. O componente implementa a interface visual; integrações de negócio devem ser conectadas ao seu sistema.\n', encoding='utf-8')
    with zipfile.ZipFile(path / 'project.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in path.rglob('*'):
            if file.name != 'project.zip' and file.is_file() and 'node_modules' not in file.relative_to(path).parts:
                archive.write(file, str(file.relative_to(path)))
    return {'summary': specification.title, 'artifacts': [p.name for p in path.iterdir() if p.is_file()], 'metadata': metadata}
