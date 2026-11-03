from datetime import date, datetime
from zoneinfo import ZoneInfo
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Norm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str = Field(pattern=r'^(LEI|LCP|DEL|DEC|CON|EMC)$')
    number: int = Field(ge=1, le=999999)
    year: int = Field(ge=1800, le=2100)
    articles: list[str] = Field(default_factory=list, max_length=8)

    @field_validator('articles')
    @classmethod
    def valid_articles(cls, values):
        if any(not re.fullmatch(r'\d{1,5}(?:-[a-z])?', v) for v in values):raise ValueError('invalid_article')
        return list(dict.fromkeys(values))


class Verification(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reference_date: date
    norms: list[Norm] = Field(min_length=1, max_length=3)


class ProcurementLimits(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reference_date:date


class Precedent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    court:str=Field(pattern=r'^(STF|STJ)$')
    kind:str=Field(pattern=r'^(TEMA|SUMULA|SV|ADI|ADC|ADPF|RE|ARE|RESP|ARESP)$')
    number:int=Field(ge=1,le=99999999)


class Research(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reference_date:date
    norms:list[Norm]=Field(default_factory=list,max_length=3)
    precedents:list[Precedent]=Field(default_factory=list,max_length=3)
    official_urls:list[str]=Field(default_factory=list,max_length=3)
    query:str=Field(default='',max_length=1200)
    subject_query:str=Field(default='',max_length=160)
    recovery_topics:list[str]=Field(default_factory=list,max_length=2)
    court:str=Field(default='',pattern=r'^(STF|STJ)?$')

    @field_validator('recovery_topics')
    @classmethod
    def public_recovery_topics(cls,values):
        for value in values:SubjectSearch(query=value)
        return values

    @field_validator('subject_query')
    @classmethod
    def subject_words(cls,value):
        if value:SubjectSearch(query=value)
        return value


class SubjectSearch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query:str=Field(min_length=3,max_length=160)

    @field_validator('query')
    @classmethod
    def public_words(cls,value):
        if any(not (c.isalpha() or c in ' -') for c in value):raise ValueError('public_topic_words_only')
        if not 1<=len(value.split())<=12:raise ValueError('bounded_topic_required')
        return value.strip()


def public_topic(text):
    """Send only bounded public subject words, never identifiers or a case narrative."""
    if len(text)>600 or re.search(r'@|https?://|\b(?:cpf|cnpj|matr[íi]cula|processo\s*\d|meu|minha|nosso|nossa|ocorreu|ocorrid\w*|contratei|contratamos|anexo|nomeado)\b',text,re.I):return ''
    text=re.sub(r'\b(?:data de refer[eê]ncia|refer[eê]ncia|data dos fatos)\s*:?\s*(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})','',text,flags=re.I)
    if re.search(r'\d',text):return ''
    text=re.sub(r'\btr[âa]nsitos\b','trânsito',text,flags=re.I)
    text=re.sub(r'\bcrime\b','crimes',text,flags=re.I)
    stop={'qual','quais','a','as','o','os','um','uma','que','lei','leis','norma','normas','legislação','legislacao','trata','tratam','sobre','de','do','da','dos','das','e','é','são','sao','para','por','no','na','nos','nas','brasil','brasileira','brasileiras','previsto','previstos','prevista','previstas','regula','regulam','existe','existem','explica','explique','me','diga','informe','pesquise','consulte','gostaria','saber','quero','hoje','atual','atualmente','acordo','com','qualquer','pode','poderia','você','voce'}
    terms=[t.casefold() for t in re.findall(r'[^\W\d_]+',text,re.UNICODE) if t.casefold() not in stop]
    generic={'faça','faca','análise','analise','jurídica','juridica','jurídico','juridico','ignore','conferência','conferencia','ferramentas','desativadas','desativada','direito','analisar'}
    terms=[t for t in terms if t not in generic]
    if not terms or len(terms)>10:return ''
    return ' '.join(dict.fromkeys(terms))[:160]


def identify_precedents(text):
    result=[]
    for m in re.finditer(r'\b(tema|s[úu]mula(?:\s+vinculante)?|ADI|ADC|ADPF|AREsp|REsp|ARE|RE)\s*(?:n[ºo°.]*\s*)?(\d[\d.]*)\b',text,re.I):
        before=text[max(0,m.start()-25):m.start()];after=text[m.end():m.end()+30]
        courts=list(re.finditer(r'\b(STF|STJ)\b',before,re.I));suffix=re.match(r'\s*(?:do|da|no|de|[-–—(])?\s*(STF|STJ)\b',after,re.I)
        kind=m[1].upper();kind='TEMA' if kind=='TEMA' else 'SV' if 'VINCULANTE' in kind else 'SUMULA' if kind.startswith(('SÚMULA','SUMULA')) else kind
        court=suffix[1].upper() if suffix else courts[-1][1].upper() if courts else ('STF' if kind in ('ADI','ADC','ADPF','RE','ARE','SV') else 'STJ' if kind in ('RESP','ARESP') else None)
        if court:
            item=Precedent(court=court,kind=kind,number=int(m[2].replace('.','')))
            if item not in result:result.append(item)
    return result[:3]


class NormSearch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:str=Field(default='LEI',pattern=r'^(LEI|LCP|DEL|DEC|EMC)$')
    number:int=Field(ge=1,le=999999)
    year:int|None=Field(default=None,ge=1800,le=2100)


class Bill(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:str=Field(default='PL',pattern=r'^(PL|PLP|PEC|MPV)$')
    number:int=Field(ge=1,le=999999)
    year:int=Field(ge=1800,le=2100)


class LegislativeHistory(BaseModel):
    model_config=ConfigDict(extra='forbid')
    bill:Bill
    reference_date:date


ALIASES = {
    'ctb':('LEI',9503,1997),'código de trânsito brasileiro':('LEI',9503,1997),
    'código penal':('DEL',2848,1940),'código de processo penal':('DEL',3689,1941),
    'lgpd':('LEI',13709,2018),'lei geral de proteção de dados':('LEI',13709,2018),
    'lei maria da penha':('LEI',11340,2006),'estatuto da criança e do adolescente':('LEI',8069,1990),
    'cpc': ('LEI', 13105, 2015), 'código de processo civil': ('LEI', 13105, 2015),
    'código civil': ('LEI', 10406, 2002), 'clt': ('DEL', 5452, 1943),
    'lindb': ('DEL', 4657, 1942), 'ctn': ('LEI', 5172, 1966),
    'código de defesa do consumidor': ('LEI', 8078, 1990), 'cdc': ('LEI', 8078, 1990),
    'lei de licitações': ('LEI', 14133, 2021),
}
LEGAL = re.compile(r'\b(crimes?|tr[âa]nsito|ctb|lgpd|tema\s*\d|s[úu]mula|STF|STJ|ADI|ADC|ADPF|jur[ií]dic\w*|jurisprud[eê]ncia|constitucional\w*|advogad\w*|direitos?|lei|leis|legisla[çc][aã]o|norma|normas|portaria|resolu[çc][aã]o|instru[çc][aã]o normativa|senten[çc]a|peti[çc][aã]o|prescri[çc][aã]o|usucapi[aã]o|licita[çc][aã]o|cpc|clt|ctn|lindb|cdc|ac[oó]rd[aã]o|mandado|recurso|minuta|processo judicial|indeniza[çc][aã]o|aposentadoria|pens[aã]o|demiss[aã]o|contrato|habeas corpus|tribut[aá]ri\w*|penal|trabalhista|previdenci[aá]ri\w*)\b', re.I)


def today():
    return datetime.now(ZoneInfo('America/Manaus')).date()


def identify(text):
    """No case narrative is sent to an external search engine."""
    text = text.lower()
    found = {}
    articles = list(dict.fromkeys(a.replace('.','') for a in re.findall(r'\bart(?:igo)?\.?\s*(\d+(?:\.\d{3})*(?:-[a-z])?)(?![\d.])', text)))[:8]
    for alias, ref in ALIASES.items():
        if re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text):
            found[ref] = Norm(kind=ref[0], number=ref[1], year=ref[2], articles=articles)
    for m in re.finditer(r'\b(lei complementar|lei|decreto-lei|decreto|emenda constitucional|ec)\s*(?:n[ºo°.]*\s*)?(\d[\d.]{0,8})\s*[/,]\s*(\d{4})\b', text):
        kind = {'lei':'LEI','lei complementar':'LCP','decreto-lei':'DEL','decreto':'DEC','emenda constitucional':'EMC','ec':'EMC'}[m[1]]
        ref = (kind, int(m[2].replace('.', '')), int(m[3]))
        found[ref] = Norm(kind=ref[0], number=ref[1], year=ref[2], articles=articles)
    return list(found.values())


def reference(text):
    # Only an explicit case/reference date; a law's own date is never selected.
    matches = re.findall(r'(?:data (?:relevante|de refer[eê]ncia|dos fatos|do fato)|fatos (?:em|de)|refer[eê]ncia)\s*[:=]?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', text, re.I)
    if matches:
        raw = matches[-1]
        try:return date.fromisoformat(raw) if '-' in raw else datetime.strptime(raw, '%d/%m/%Y').date()
        except ValueError:return None
    if re.search(r'\b(hoje|atualmente|data atual|red[aã][çc][aã]o atual|vigente hoje)\b', text, re.I):
        return today()
    return None
