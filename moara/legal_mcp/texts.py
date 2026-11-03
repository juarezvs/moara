"""Current compilations explicitly linked by the official norm catalogue."""
import re,unicodedata
import httpx
from html.parser import HTMLParser
from urllib.parse import urlsplit
from .contracts import today

# Source locations only, never prewritten answers or stored monetary values.
CURRENT_ALTERNATIVES={('LEI',8112,1990):['https://www2.camara.leg.br/legin/fed/lei/1990/lei-8112-11-dezembro-1990-322161-normaatualizada-pl.html'],
    ('LEI',8213,1991):['https://www2.camara.leg.br/legin/fed/lei/1991/lei-8213-24-julho-1991-363650-normaatualizada-pl.html']}

class LegalHTML(HTMLParser):
    def __init__(self,html):
        super().__init__(convert_charrefs=True);self.parts=[];self.ignored=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','s','strike','del'):self.ignored.append(tag)
        if tag in ('p','div','br','tr','h1','h2','h3'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in self.ignored:self.ignored.remove(tag)
        if tag in ('p','div','tr','h1','h2','h3'):self.parts.append('\n')
    def handle_data(self,text):
        if not self.ignored:self.parts.append(text)
    def text(self):return re.sub(r'[ \t\r\f\v]+',' ',''.join(self.parts))

def folded(text):return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))

def articles_from_html(html,source,articles,at):
    if at!=today():raise ValueError('current_compilation_is_not_historical_evidence')
    text=LegalHTML(html).text()
    # Source line wraps can put an inline "art. 2º da Lei ..." at the start
    # of a line. It is a cross-reference, not a new article boundary.
    matches=list(re.finditer(r'(?:^|\n)\s*(?:Art|ART)\.?\s*(\d+(?:\.\d{3})*(?:-[A-Za-z])?)[º°o]?\b',text))
    result=[];seen=set()
    for i,m in enumerate(matches):
        article=m[1].replace('.','').lower()
        if articles and article not in articles:continue
        body=re.sub(r'\s+',' ',text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)]).strip()
        if len(body)<12 or article in seen:continue
        seen.add(article)
        result.append({'device':'art'+article,'name':'Art. '+article,'text':body[:8000],
            'source':source,'version_date':str(at),'version_date_basis':'retrieval_date_not_amendment_or_effective_date',
            'effective_date_confirmed':False,'text_truncated':len(body)>8000,'text_basis':'official_current_compilation'})
    if not result:raise ValueError('no_articles_in_official_compilation')
    return result

async def current_encoding(adapter,structured,spec,at,result):
    from .sources import sequence
    from .catalog import tracked
    if at!=today():return []
    urn=structured.get('legislationIdentifier','')
    for encoding in sequence(structured.get('encoding')):
        url=encoding.get('contentUrl','');uri=urlsplit(url)
        identity=(encoding.get('encodesCreativeWork') or {}).get('@id','')
        if encoding.get('version')!='Current' or not identity.startswith('https://normas.leg.br/?urn='+urn+'@'):continue
        if uri.scheme!='https' or uri.hostname!='normas.leg.br' or not re.fullmatch(r'/api/binario/[0-9a-f-]{36}/texto',uri.path):continue
        html=await tracked(adapter,url,result,'html')
        excerpts=articles_from_html(html,url,spec.articles,at)
        result['text_selection_basis']='official_current_compilation_retrieved_now'
        result['gaps'].append('A compilação corrente foi consultada agora; a data de recuperação não é data de alteração ou entrada em vigor. Não foi usada para fatos históricos.')
        return excerpts
    return []

async def alternative_current(adapter,spec,at,result):
    from .catalog import tracked
    from .sources import planalto_path
    if at!=today():return []
    try:
        from .discovery import current_camara
        excerpts=await current_camara(adapter,spec,at,result)
        if excerpts:return excerpts
    except (httpx.HTTPError,ValueError,TypeError,KeyError):pass
    urls=list(CURRENT_ALTERNATIVES.get((spec.kind,spec.number,spec.year),[]))
    path=planalto_path(spec)
    if path and not urls:
        urls=['https://www.planalto.gov.br/ccivil_03/'+path.replace('.htm','compilado.htm'),'https://www.planalto.gov.br/ccivil_03/'+path]
    for url in urls[:2]:
        try:
            html=await tracked(adapter,url,result,'html');head=LegalHTML(html).text()[:6000]
            digits=re.sub(r'(?<=\d)\.(?=\d)','',head)
            if not re.search(r'\b'+str(spec.number)+r'\b',digits) or str(spec.year) not in head:raise ValueError('alternative_identity_mismatch')
            excerpts=articles_from_html(html,url,spec.articles,at)
            result.update(source=url,text_selection_basis='official_current_compilation_retrieved_now',status='official_text_retrieved')
            result['gaps'].append('Consultada compilação corrente em fonte oficial alternativa. A recuperação atual não certifica aplicabilidade histórica ou cobertura exaustiva de alterações.')
            return excerpts
        except (httpx.HTTPError,ValueError,TypeError):continue
    return []

def relevant(excerpts,query,limit=12):
    # Full norm is scanned BEFORE limiting the model context. Avoid the former
    # first-100-articles cutoff that silently hid later relevant provisions.
    stop={'acordo','lei','artigo','art','explique','mostre','sobre','como','para','pela','pelo','quais','qual','isso','isto','uma','com','que','hoje','atual','previsto','prevista','informe','norma'}
    stop|={'trata','tratam','faca','fazer','diz','gostaria','numero','referencia','referente','preciso','brasileira','brasileiras','legislacao','pesquise','consulte'}
    stop|={'diferenca','diferencas','entre','compare','comparar','distincao','explique','explicar','entenda'}
    def stem(t):
        if t.endswith('oes'):return t[:-3]+'ao'
        return t[:-1] if len(t)>4 and t.endswith('s') else t
    terms={stem(t) for t in re.findall(r'[a-z]{3,}',folded(query)) if t not in stop}
    import math
    documents=[{stem(w) for w in re.findall(r'[a-z]{3,}',folded(x['text']))} for x in excerpts]
    weight={t:1+math.log((1+len(excerpts))/(1+sum(t in words for words in documents))) for t in terms}
    def score(e):
        text=folded(e['text']);words={stem(w) for w in re.findall(r'[a-z]{3,}',text)}
        # Distinctive concepts outrank generic words such as servidor. Prefix
        # matching confused requisicao with requisitos and favoured huge articles.
        opening=re.sub(r'^art\.?\s*\d+(?:-[a-z])?[º°o.]?\s*','',text)
        definitions=sum(6 for t in terms if re.search(r'^(?:a |o |as |os )?'+re.escape(t)+r'\s+(?:e\b|consiste\b|significa\b|compreende\b)',opening))
        return definitions+sum(weight[t] for t in terms if t in words)
    ranked=sorted(enumerate(excerpts),key=lambda item:(-score(item[1]),item[0]))
    # A matching caput often states the topic while its incisos/alíneas contain
    # the actual conditions. Preserve that context instead of dropping it for
    # not repeating the search words.
    selected=[];seen=set()
    def add(e):
        if e['device'] not in seen and len(selected)<limit:selected.append(e);seen.add(e['device'])
    for _,e in ranked:
        if score(e)<=0:continue
        for parent in excerpts:
            if e['device'].startswith(parent['device']+'_'):add(parent)
        add(e)
        if e['device'].endswith('_cpt') or re.search(r'_par\d+$',e['device']):
            for child in [c for c in excerpts if c['device'].startswith(e['device']+'_')][:12 if limit>12 else 6]:add(child)
        if len(selected)>=limit:break
    return selected or excerpts[:min(limit,4)]
