"""Deterministic chat answers from the already-authorized execution catalog."""
import re
import unicodedata
from common.policy import allowed_objects


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))


def answer(question, rows):
    text=normalize(question)
    listing=bool(re.search(r'\b(qual|quais|liste|listar|mostre|mostrar|exiba|disponiveis|posso|consigo|consegue|pode|tem|possui|conectad\w*)\b',text))
    sources=bool(re.search(r'\b(fontes?|conectores?|bancos?)\b',text))
    objects=bool(re.search(r'\b(tabelas|objetos|catalogos?|schemas?|esquemas?)\b|quais dados|dados disponiveis',text))
    capability=bool(re.search(r'\b(consultar|acessar|consulta|acesso|consultas)\b',text))
    if not listing or not (sources or objects or capability):return None
    # A question requesting actual rows/aggregates belongs to the query planner.
    if re.search(r'\b(registros|servidores|pessoas|total|quantos|quantas|media|soma|where|select)\b',text):return None
    citations=[{'id':str(r['id']),'name':r['name'],'objects':sorted(allowed_objects(r['policy']))} for r in rows]
    if not rows:
        return {'handled':True,'answer':'Não há fontes ativas autorizadas para esta sessão ou para a seccional informada.','sources':[],'execution_mode':'authorized_catalog'}
    if objects:
        lines=['Objetos autorizados no catálogo atual:']
        for r in rows:
            names=sorted(allowed_objects(r['policy']))
            lines.append('**'+r['name']+'**: '+(', '.join('`'+n+'`' for n in names[:100]) or 'nenhum objeto liberado')+'.')
            if len(names)>100:lines.append(f'Exibidos 100 de {len(names)} objetos; consulte o catálogo na Central para a lista completa.')
        lines.append('Esta lista contém os objetos liberados à IA, não todas as tabelas existentes no banco. Nenhum registro foi consultado.')
    else:
        lines=['Posso consultar as seguintes fontes ativas autorizadas, em modo somente leitura:']
        lines.extend('- **'+r['name']+'** ('+r['kind']+'). Objetos liberados: '+str(len(allowed_objects(r['policy'])))+'.' for r in rows)
        lines.append('Informe a seccional e o que deseja consultar. Posso listar os objetos autorizados e executar consultas dentro das permissões da sua sessão.')
    return {'handled':True,'answer':'\n\n'.join(lines),'sources':citations,'execution_mode':'authorized_catalog'}
