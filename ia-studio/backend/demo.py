from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(docs_url=None, redoc_url=None)
WRITES = 0
PAGES = {
    '/': ('Visão geral', 'Acompanhe sua jornada de trabalho', ['Jornada prevista', 'Horas registradas', 'Saldo de horas']),
    '/minha-jornada': ('Minha Jornada', 'Consulte os horários e a jornada do período', ['Entrada', 'Intervalo', 'Saída']),
    '/espelho': ('Espelho de Ponto', 'Confira as marcações registradas', ['Data', 'Primeira entrada', 'Última saída']),
    '/banco-horas': ('Banco de Horas', 'Visualize créditos, débitos e saldo', ['Crédito', 'Débito', 'Saldo']),
    '/solicitacoes': ('Solicitações', 'Consulte solicitações e seus estados', ['Protocolo', 'Tipo de solicitação', 'Situação']),
}

@app.get('/health')
async def health():
    return {'ok': True}

@app.get('/__counter')
async def counter():
    return {'writes': WRITES}

@app.post('/danger')
async def danger():
    global WRITES
    WRITES += 1
    return {'writes': WRITES}

@app.get('/{path:path}', response_class=HTMLResponse)
async def page(path: str):
    title, subtitle, fields = PAGES.get('/' + path, ('Página não encontrada', 'Use o menu da demonstração', []))
    links = ''.join(f'<a href="{url}">{details[0]}</a>' for url, details in PAGES.items())
    cards = ''.join(f'<div class="card"><label>{label}</label><strong>{value}</strong><small>Exemplo do período</small></div>' for label, value in zip(fields, ['160h', '154h', '+06h']))
    rows = ''.join(f'<tr><td>0{i+1}/10/2026</td><td>08:00</td><td>17:00</td><td>Registrado</td></tr>' for i in range(4))
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Demonstração Moara Studio</title><style>
    *{{box-sizing:border-box}}body{{margin:0;font:14px Arial,sans-serif;color:#1a3454;background:#f3f6fb}}aside{{position:fixed;inset:0 auto 0 0;width:230px;padding:35px 22px;background:#11233d;color:#acbfd8}}aside h2{{color:white;margin-bottom:35px;font-size:20px}}a{{display:block;text-decoration:none;color:inherit;padding:14px;border-radius:6px}}a:hover{{background:#ffffff15}}main{{margin-left:230px;padding:40px}}.badge{{background:#e6f1ff;color:#2563eb;border-radius:20px;padding:7px 12px;font-size:10px}}h1{{font-size:30px;margin-top:30px}}p{{color:#71839b}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin:30px 0}}.card,.panel{{background:white;border:1px solid #e0e7f0;border-radius:10px;padding:25px}}.card strong{{display:block;font-size:29px;margin:17px 0}}label,small{{font-size:11px;color:#70839c}}.panel{{margin-top:20px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:15px;border-bottom:1px solid #e5ebf4;text-align:left;font-size:12px}}select{{padding:10px;border:1px solid #cfdaea;border-radius:6px}}button{{padding:10px 13px;border:1px solid #d8e2f0;border-radius:6px;background:#fff;color:#59718e}}footer{{font-size:10px;color:#7e91aa;margin-top:28px}}@media(max-width:700px){{aside{{position:static;width:100%;padding:14px}}aside h2{{margin:8px}}aside a{{display:inline-block;font-size:11px;padding:8px}}main{{margin:0;padding:20px}}.cards{{gap:10px}}.card{{padding:15px}}.card strong{{font-size:21px}}}}
    </style><body><aside><h2>Moara Studio · Demo</h2>{links}</aside><main><span class="badge">AMBIENTE CONTROLADO · DADOS FICTÍCIOS</span><h1>{title}</h1><p>{subtitle}</p><label for="periodo">Período de consulta</label> <select id="periodo"><option>Outubro de 2026</option><option>Setembro de 2026</option></select><div class="cards">{cards}</div><section class="panel"><h2>Registros de demonstração</h2><table><tr><th>Data</th><th>Entrada</th><th>Saída</th><th>Situação</th></tr>{rows}</table></section><section class="panel"><p data-private>Usuário de teste: pessoa.teste@example.local</p><form action="/danger" method="post"><button type="submit">Salvar alteração de teste</button></form></section><footer>Aplicação de demonstração criada para testes do Moara Studio. Não representa o SECP real.</footer></main></body></html>'''
