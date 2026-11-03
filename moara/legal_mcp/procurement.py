"""Literal official procurement tables, distinct from a legal opinion.

Never contains monetary constants. A fresh PNCP index must agree with the
official table's decree and exercise; stale/ambiguous tables fail closed.
"""
import re
from datetime import date,datetime,timezone
from html.parser import HTMLParser
import httpx
from .sources import OfficialSources,clean,extract
from .contracts import today

INDEX='https://www.gov.br/pncp/pt-br/pncp/legislacao/decretos'
TABLE='https://www.gov.br/compras/pt-br/acesso-a-informacao/comunicados/2025/no-47-25-decreto-altera-valores-da-lei-14-133-para-compras-publicas'
BASIS_URN='urn:lex:br:federal:lei:2021-04-01;14133'
BASIS='https://normas.leg.br/api/public/normas?urn='+BASIS_URN+'&&tipo_documento=maior-detalhe'

class Document(HTMLParser):
    def __init__(self,html):
        super().__init__(convert_charrefs=True);self.rows=[];self.row=None;self.cell=None;self.links=[];self.anchor=None;self.text=[];self.skip=0;self.feed(html)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style'):self.skip+=1
        if tag=='tr':self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=[]
        if tag=='a':self.anchor=[attrs.get('href',''),[]]
    def handle_data(self,data):
        if self.skip:return
        self.text.append(data)
        if self.cell is not None:self.cell.append(data)
        if self.anchor is not None:self.anchor[1].append(data)
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if tag in ('td','th') and self.cell is not None:
            self.row.append(clean(' '.join(self.cell)));self.cell=None
        if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None
        if tag=='a' and self.anchor is not None:
            self.links.append((self.anchor[0],clean(' '.join(self.anchor[1]))));self.anchor=None

def decree(text):
    m=re.search(r'decreto\s*(?:n[.º°o\s]*)?(\d[\d.]*)\s*,?\s*de\s*\d{1,2}\s*de\s*\w+\s*de\s*(\d{4})',text,re.I)
    return (int(m[1].replace('.','')),int(m[2])) if m else None

def extract_limits(index_html,table_html,at):
    index=Document(index_html);table=Document(table_html);text=clean(' '.join(table.text))
    if not re.search(r'14[.]?133',text):raise ValueError('wrong_law')
    # Isolate the article body before interpreting dates or decree references.
    body=re.search(r'<div[^>]+id=["\']parent-fieldname-text["\'][^>]*>(.*)',table_html,re.S|re.I)
    if body:text=clean(' '.join(Document(body[1]).text))
    effective=re.findall(r'(?:vigor|vigência)\s+a?\s*partir\s+de\s+1[º°o]?\s+de\s+janeiro\s+de\s+(\d{4})',text,re.I)
    if len(set(effective))!=1:raise ValueError('effective_exercise_not_explicit')
    year=int(effective[0]);starts=date(year,1,1)
    if at!=today() or at.year!=year:raise ValueError('current_table_cannot_establish_requested_historical_or_future_values')
    reported=decree(text)
    indexed=[(url,decree(label)) for url,label in index.links if decree(label)]
    if not reported or not indexed:raise ValueError('decree_not_identified')
    # The PNCP page is a bounded index; do not claim a complete DOU search.
    latest=max((ref for _,ref in indexed),key=lambda ref:(ref[1],ref[0]))
    if latest!=reported:raise ValueError('pncp_and_table_decree_disagree')
    dou=next((url for url,ref in indexed if ref==reported and url.startswith('https://www.in.gov.br/')),None)
    if not dou:raise ValueError('official_publication_link_missing')
    rows=[]
    for row in table.rows:
        if len(row)!=2:continue
        m=re.match(r'Art\.?\s*75[º°o]?\s*,\s*(?:caput\s*,\s*)?inciso\s+(II|I)(?=\s*[:;,.]|$)',row[0],re.I)
        if not m:continue
        amounts=re.findall(r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)',row[1])
        if len(set(amounts))!=1:raise ValueError('ambiguous_amount')
        rows.append({'device':'Art. 75, inciso '+m[1].upper(),'inciso':m[1].upper(),'amount_brl':amounts[0],
                     'official_label':row[0],'official_text':row[1],'source':TABLE})
    if sorted(r['inciso'] for r in rows)!=['I','II']:raise ValueError('missing_or_duplicate_limit')
    return {'rows':rows,'effective_from_as_reported':str(starts),'exercise':year,
            'updating_act':{'kind':'DEC','number':reported[0],'year':reported[1],'publication_link':dou}}

async def consult(client,spec):
    result={'status':'official_information_unavailable','reference_date':str(spec.reference_date),
            'checked_at':datetime.now(timezone.utc).isoformat(),'legal_conclusion_allowed':False,
            'information_only':True,'rows':[],'snapshots':[],'source_checks':[],'gaps':[]}
    if spec.reference_date!=today():
        result['gaps'].append('A tabela corrente não comprova limites históricos ou futuros. É necessária pesquisa dos atos aplicáveis à data solicitada.')
        return result
    adapter=OfficialSources(client)
    try:
        pages=[]
        for url in [INDEX,TABLE]:
            html,snapshot=await adapter.fetch(url,'html');pages.append(html);result['snapshots'].append(snapshot)
            result['source_checks'].append({'url':url,'status':'retrieved','sha256':snapshot['sha256']})
        values=extract_limits(*pages,spec.reference_date)
        law,snapshot=await adapter.fetch(BASIS)
        result['snapshots'].append(snapshot)
        if law.get('legislationIdentifier')!=BASIS_URN:raise ValueError('law_identity_mismatch')
        excerpts,_=extract(law,['75'],str(spec.reference_date))
        inferior=[e for e in excerpts if re.search(r'valores\s+inferiores',e['text'],re.I)]
        if len(inferior)<2:raise ValueError('statutory_comparison_not_retrieved')
        result.update(values,basis_source='https://normas.leg.br/?urn='+BASIS_URN,basis_excerpts=inferior[:2])
        result['source_checks'].append({'url':BASIS,'status':'retrieved','sha256':snapshot['sha256']})
        result['status']='official_information_retrieved'
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        result['gaps'].append('Não foi possível conferir uma tabela oficial atual compatível com o índice do PNCP e a data solicitada. Nenhum valor antigo será apresentado como atual.')
    result['gaps'].append('Consulta informativa à tabela divulgada pelo Governo Federal e ao índice do PNCP; não certifica cobertura exaustiva do DOU, decisões judiciais ou autorização para dispensar uma contratação concreta.')
    return result
