"""Choose the application or upstream SARH explicitly; never expand authorization."""
import re,unicodedata

def normalized(question):return ''.join(c for c in unicodedata.normalize('NFKD',question.casefold()) if not unicodedata.combining(c))

def select(question,rows):
    text=normalized(question)
    mentioned=set(re.findall(r'\b(?:SJ[A-Z]{2}|JFAM)\b',question.upper()))
    application=bool(re.search(r'\bsecp\b|\bferias\b|banco de horas|banco horas|\b(homologa\w*|marcacoes?|apurac\w*|espelhos?|solicitacoes?|recesso\w*|jornadas?|escalas?)\b|horas extras|controle de ponto',text))
    oracle=bool(re.search(r'\b(oracle|sarh)\b',text)) and 'secp' not in text
    absences=bool(re.search(r'\b(afastad\w*|afastamentos?|licencas?)\b',text))
    available=[r for r in rows if (r.get('semantic') or {}).get('dataset')=='secp_application']
    if not application and not oracle and not absences and available and re.search(r'\b(servidores?|funcionarios?|cargos?|lotacoes?)\b',text):application=True
    if oracle:rows=[r for r in rows if r['kind']=='oracle']
    elif application:
        if len(mentioned)==1:rows=[r for r in available if (r.get('semantic') or {}).get('organization') in mentioned]
        else:
            consolidated=[r for r in available if (r.get('semantic') or {}).get('organization_scope') and mentioned<=set(r['semantic']['organization_scope'])]
            rows=consolidated or (available if not mentioned else [])
        return rows
    elif absences:rows=[r for r in rows if r['kind']=='oracle']
    if mentioned:rows=[r for r in rows if (r.get('semantic') or {}).get('organization') in mentioned]
    return rows
