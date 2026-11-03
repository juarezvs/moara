"""Bounded official HTTP sources. Temporal text is NOT an effective-date finding."""
import asyncio, base64, gzip, hashlib, json, re, time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlsplit,parse_qs
from urllib.parse import urlencode
import httpx
from .contracts import today

HOSTS = {'legis.senado.leg.br', 'normas.leg.br', 'www.planalto.gov.br', 'www.in.gov.br', 'portal.stf.jus.br','dadosabertos.camara.leg.br','www.gov.br','www.camara.leg.br','www2.camara.leg.br','scon.stj.jus.br','www.stj.jus.br','atos.cnj.jus.br','www.cnj.jus.br','www.cjf.jus.br'}
MAX_BYTES = 12 * 1024 * 1024


def sequence(value):
    # Official JSON-LD arrays may mix references, nulls and object records.
    return [v for v in value if isinstance(v,dict)] if isinstance(value, list) else [value] if isinstance(value, dict) else []


def clean(value):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))).strip()


def mapping(value):return value if isinstance(value,dict) else {}


class OfficialSources:
    def __init__(self, client):
        self.client = client
        # Shared by every verification/tool using this service client.
        if not hasattr(client,'_moara_official_slots'):
            client._moara_official_slots=asyncio.Semaphore(2)
            client._moara_official_rates={}
        self.slots=client._moara_official_slots

    async def fetch(self, url, expected='json'):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443):
            raise ValueError('unapproved_official_source')
        # Redirects deliberately fail closed; no arbitrary URLs or private case queries.
        async with self.slots:
            rate=self.client._moara_official_rates.setdefault(parsed.hostname,{'lock':asyncio.Lock(),'next':0})
            async with rate['lock']:
                await asyncio.sleep(max(0,rate['next']-time.monotonic()))
                rate['next']=time.monotonic()+.35
            async with self.client.stream('GET', url, timeout=15, follow_redirects=False,
                headers={'User-Agent':'Moara-LegalVerification/2.0','Cache-Control':'no-cache','Pragma':'no-cache', 'Accept':'application/json' if expected=='json' else 'text/html'}) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_BYTES:raise ValueError('official_response_too_large')
                raw = bytes(content)
                if expected == 'json':
                    data = json.loads(raw)
                    if not isinstance(data, dict):raise ValueError('unexpected_official_document')
                else:
                    data = raw.decode(response.encoding or 'utf-8', errors='replace')
                    if len(clean(data)) < 100:raise ValueError('empty_official_document')
                return data, {'url':url, 'retrieved_at':datetime.now(timezone.utc).isoformat(),
                    'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw),
                    'content_type':response.headers.get('content-type',''),
                    'etag':response.headers.get('etag'),'last_modified':response.headers.get('last-modified'),
                    'server_date':response.headers.get('date'),'retrieval_policy':'network_no_stale_fallback',
                    'snapshot_gzip_base64':base64.b64encode(gzip.compress(raw, mtime=0)).decode()}

    async def norm(self, spec, at, enrich=True):
        from .catalog import tracked,unique,related_changes,originating_bill,history,history_record,publication_date
        from .contracts import LegislativeHistory
        result = {'norm':spec.model_dump(), 'reference_date':at.isoformat(), 'status':'unconfirmed',
                  'excerpts':[], 'changes':[], 'jurisprudence':[], 'snapshots':[], 'source_checks':[], 'gaps':[]}
        structured=None
        try:
            url=f'https://legis.senado.leg.br/dadosabertos/legislacao/{spec.kind}/{spec.number}/{spec.year}.json'
            metadata=await tracked(self,url,result)
            docs = sequence(mapping(mapping(metadata.get('DetalheDocumento')).get('documentos')).get('documento'))
            # Never silently select an ambiguous norm or search-error payload.
            if len(docs) != 1:raise ValueError('ambiguous_or_missing_norm')
            doc = docs[0]; ident = doc['identificacao']
            urn=validated_identity(ident,spec)
            result.update(name=ident.get('normaNome'), summary=clean(doc.get('ementa')), publication=doc.get('publicacoes'), notes=doc.get('observacao'))
            result['source'] = 'https://normas.leg.br/?urn='+urn
            result['changes'] = [{**row,'after_reference_date':when>str(at) if (when:=publication_date(row.get('datapub'))) else None}
                for row in unique(sequence(mapping(doc.get('vides')).get('vide')))]
            for item in sequence(mapping(doc.get('disps')).get('disp')):
                name = item.get('nomeDispositivo','')
                if spec.articles and not any(re.search(r'Art\.\s*'+re.escape(a)+r'(?![\dA-Za-z])', name, re.I) for a in spec.articles):continue
                for ref in sequence(mapping(item.get('refs')).get('ref')):
                    if re.search(r'ADI|ADPF|ADC|Ac[oó]rd[aã]o|constitucional|Supremo', json.dumps(ref,ensure_ascii=False), re.I):
                        result['jurisprudence'].append({'device':name, **ref, 'effects_status':'not_confirmed', 'source':url})
            structured=await tracked(self,'https://normas.leg.br/api/public/normas?urn='+urn+'&&tipo_documento=maior-detalhe',result)
            if structured.get('legislationIdentifier') != urn:raise ValueError('structured_norm_identity_mismatch')
            result['dataset_modified_as_reported']=structured.get('dateModified')
            result['text_selection_basis']='official_version_dates_not_effective_dates'
            result['excerpts'], issues = extract(structured, spec.articles, at.isoformat())
            if not result['excerpts']:
                from .texts import current_encoding
                result['excerpts']=await current_encoding(self,structured,spec,at,result)
            result['gaps'].extend(issues)
            result['status'] = 'official_text_retrieved' if result['excerpts'] else 'unconfirmed'
            result['gaps'].append('A cronologia das redações não comprova, por si só, entrada em vigor, transição ou eficácia no caso concreto.')
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            structured=None
            result['gaps'].append('Não foi possível confirmar a norma e sua redação nas fontes oficiais consultadas.')
        if not result['excerpts']:
            from .texts import alternative_current
            result['excerpts']=await alternative_current(self,spec,at,result)
        if structured is not None and enrich:
            related={'checks':[],'snapshots':[],'source_checks':[],'coverage_complete':False}
            try:await asyncio.wait_for(related_changes(self,result['changes'],spec.articles,at,related),12)
            except TimeoutError:related['status']='unavailable'
            result['snapshots'].extend(related.pop('snapshots'));result['source_checks'].extend(related.pop('source_checks'))
            result['related_norm_verification']=related
            result['gaps'].append('Alterações correlatas: conferência limitada às duas referências normativas mais recentes elegíveis retornadas pelo Senado; não comprova ausência de outras alterações.')
            bill=originating_bill(structured)
            if bill:
                historical_spec=LegislativeHistory(bill=bill,reference_date=at);record=history_record(historical_spec)
                try:await asyncio.wait_for(history(self,historical_spec,record),30)
                except TimeoutError:
                    record['status']='unavailable'
                    record['gaps'].append('Tempo limite da consulta à Câmara. Evidências parciais preservadas; essa indisponibilidade não certifica a ausência de tramitações.')
                result['snapshots'].extend(record.pop('snapshots'));result['source_checks'].extend(record.pop('source_checks'))
                result['legislative_history']=record
            else:result['legislative_history']={'status':'not_identified','normative_text':False,'gaps':['Proposição da Câmara não identificada de modo explícito na proveniência oficial da norma.']}
        result['gaps'].append('Pesquisa jurisprudencial não exaustiva: referências do Senado não certificam trânsito em julgado ou modulação de efeitos.')
        # These consultations are recorded independently. A 403 or a search
        # portal shell cannot be misrepresented as an actual publication check.
        urls=[('DOU','https://www.in.gov.br/consulta/-/buscar/dou?'+urlencode({'q':f'"{spec.number}" "{spec.year}"'}))] if enrich else []
        path=planalto_path(spec)
        if path and enrich:urls.append(('Planalto','https://www.planalto.gov.br/ccivil_03/'+path))
        if spec.kind=='LEI' and spec.number==9868 and spec.year==1999 and '27' in spec.articles:
            urls.append(('STF','https://portal.stf.jus.br/constituicao-supremo/leis-infraconstitucionais/verlegislacao.asp?item=346'))
        async def probe(label,url):
            attempt={'source':label,'url':url,'attempted_at':datetime.now(timezone.utc).isoformat()}
            try:
                text,snapshot=await asyncio.wait_for(self.fetch(url,'html'),8)
                attempt.update(status='retrieved_not_certified',sha256=snapshot['sha256'])
                if label=='DOU':
                    script=re.search(r'<script[^>]*type="application/json"[^>]*>\s*(\{"jsonArray".*?\})\s*</script>',text,re.S)
                    if script:
                        payload=json.loads(script[1])
                        attempt['search_hits']=[{k:clean(hit.get(k)) for k in ('title','pubDate','editionNumber','pubName','numberPage','urlTitle','content')}
                                                for hit in payload.get('jsonArray',[])[:20]]
                        attempt['note']='Resultados da busca podem apenas mencionar a norma; não são publicações normativas confirmadas.'
                # Keep source bytes for review, but never use portal navigation
                # as normative text or as a finding of no additional changes.
                return attempt,snapshot
            except httpx.HTTPStatusError as error:
                attempt.update(status='unavailable',http_status=error.response.status_code)
            except (httpx.HTTPError,ValueError,TimeoutError):attempt['status']='unavailable'
            return attempt,None
        for attempt,snapshot in await asyncio.gather(*(probe(label,url) for label,url in urls)):
            result['source_checks'].append(attempt)
            if snapshot:result['snapshots'].append(snapshot)
        return result


def planalto_path(spec):
    if spec.kind!='LEI':return None
    number=str(spec.number)
    if spec.year>=2004:
        start=2004 if spec.year<2007 else 2007+((spec.year-2007)//4)*4
        end=2006 if start==2004 else start+3
        return f'_ato{start}-{end}/{spec.year}/lei/l{number}.htm'
    if spec.year>=2000:return f'leis/{spec.year}/l{number}.htm'
    return f'leis/l{number}.htm'


def validated_identity(ident,spec):
    uri=urlsplit(ident['urlDocumento'])
    if uri.scheme!='https' or uri.hostname!='normas.leg.br' or uri.username or uri.port not in (None,443):raise ValueError('invalid_norm_source')
    urns=parse_qs(uri.query).get('urn',[])
    if len(urns)!=1:raise ValueError('ambiguous_norm_identifier')
    urn=urns[0]
    match=re.fullmatch(r'urn:lex:br:federal:([a-z.]+):(\d{4}-\d{2}-\d{2});(\d+)',urn)
    kinds={'LEI':'lei','LCP':'lei.complementar','DEL':'decreto.lei','DEC':'decreto','EMC':'emenda.constitucional','CON':'constituicao'}
    if not match or match[1]!=kinds.get(spec.kind) or int(match[3])!=spec.number or int(match[2][:4])!=spec.year:raise ValueError('norm_identity_mismatch')
    datetime.strptime(match[2],'%Y-%m-%d')
    if int(str(ident['numero']).replace('.',''))!=spec.number or str(ident['tipo']).split('-')[0]!=spec.kind:raise ValueError('norm_identity_mismatch')
    if datetime.strptime(ident['dataassinatura'],'%d/%m/%Y').date().isoformat()!=match[2]:raise ValueError('norm_signature_date_mismatch')
    return urn


def extract(root, articles, at):
    """Select text by official version dates. Never label these dates as vigência."""
    result=[]; issues=[]; seen=set();base=root.get('legislationIdentifier')
    def walk(node, selected=False):
        for n in sequence(node):
            identifier=n.get('legislationIdentifier','')
            tail=identifier.split('!')[-1]
            if base and identifier and identifier!=base and not identifier.startswith(base+'!'):continue
            if re.search(r'(?:^|_)alt\d+',tail):
                if selected:issues.append('Texto de alteração de outra norma exige consulta separada à norma alterada: '+tail)
                continue
            # Only article nodes from the norm itself, never amendment blocks.
            hit=bool(re.fullmatch(r'art\d+(?:-[a-z])?', tail)) and (not articles or tail[3:] in articles)
            is_selected=selected or hit
            if is_selected:
                versions=sequence(n.get('workExample'))
                eligible=[v for v in versions if re.fullmatch(r'\d{4}-\d{2}-\d{2}',v.get('legislationDate','')) and v['legislationDate']<=at]
                if eligible:
                    chosen=max(eligible,key=lambda v:v['legislationDate'])
                    same=[v for v in eligible if v['legislationDate']==chosen['legislationDate']]
                    if len(same)>1:issues.append('Múltiplos eventos na mesma data exigem revisão: '+tail)
                    if chosen.get('text') and identifier not in seen:
                        text=clean(chosen['text'])
                        if text:
                            seen.add(identifier)
                            result.append({'device':tail,'name':clean(chosen.get('name',tail)), 'text':text[:8000],
                                'version_date':chosen['legislationDate'], 'source':chosen.get('@id',n.get('@id')),
                                'text_truncated':len(text)>8000,
                                'temporal_coverage':chosen.get('temporalCoverage'), 'legal_force_as_reported':chosen.get('legislationLegalForce'),
                                'amendment':chosen.get('legislationConsolidates'), 'effective_date_confirmed':False,
                                'versions':[{'date':v.get('legislationDate'),'source':v.get('@id'),'type':v.get('legislationType'),
                                             'legal_force':v.get('legislationLegalForce')} for v in versions]})
            walk(n.get('hasPart'),is_selected)
    walk(root)
    if len(result)>2000:issues.append('Trechos limitados a 2000 dispositivos nesta resposta; confira o texto integral na fonte.');result=result[:2000]
    for article in articles:
        if not any(e['device']=='art'+article or e['device'].startswith('art'+article+'_') for e in result):
            issues.append('Artigo não localizado na data de referência: '+article)
    return result, list(dict.fromkeys(issues))


async def verify(client, request):
    at=request.reference_date
    if at>today():
        return {'status':'unconfirmed','reference_date':at.isoformat(),'norms':[],'legal_conclusion_allowed':False,'gaps':['Não é possível certificar antecipadamente uma redação futura.']}
    adapter=OfficialSources(client)
    norms=await asyncio.gather(*(adapter.norm(n,at) for n in request.norms))
    # Independent publication/jurisprudence coverage is explicit; an unavailable
    # source is never converted to an assertion that no changes/decisions exist.
    return {'schema_version':2, 'status':'verification_incomplete','reference_date':at.isoformat(),
        'checked_at':datetime.now(timezone.utc).isoformat(), 'norms':norms,
        'gaps':['Vigência e eficácia não certificadas: necessária revisão das publicações e regras de transição.',
                'DOU (incluindo extras e suplementos) e Planalto: tentativas registradas; recuperação HTTP não certifica cobertura nem ausência de alterações.',
                'STF: referências constitucionais do Senado; inteiro teor, embargos e modulação ainda exigem conferência.',
                'Cobertura inicial federal. Normas estaduais e municipais não estão certificadas.'],
        'legal_conclusion_allowed':False}
