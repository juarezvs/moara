import hashlib,re,base64,gzip
from urllib.parse import urlsplit,parse_qs,urlencode,urlunsplit,quote
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

AGENT='Moara-SourceDiscovery/0.1'
OFFICIAL={'legis.senado.leg.br','normas.leg.br','www.planalto.gov.br','www.in.gov.br','portal.stf.jus.br','jurisprudencia.stf.jus.br','dadosabertos.camara.leg.br','www.gov.br','www.camara.leg.br','www2.camara.leg.br','scon.stj.jus.br','www.stj.jus.br','atos.cnj.jus.br','www.cnj.jus.br','www.cjf.jus.br'}

class NormReference(BaseModel):
 model_config=ConfigDict(extra='forbid')
 kind:str=Field(pattern='^(LEI|LCP|DEL|DEC|CON)$')
 number:int=Field(ge=1,le=999999)
 year:int=Field(ge=1800,le=2100)

class PublicSearch(BaseModel):
 model_config=ConfigDict(extra='forbid')
 topic:str=Field(default='',max_length=160)
 norms:list[NormReference]=Field(default_factory=list,max_length=2)
 @field_validator('topic')
 @classmethod
 def public_words(cls,value):
  if not value:return value
  if any(not(c.isalpha() or c in ' -') for c in value) or not 1<=len(value.split())<=12:raise ValueError('public_subject_words_required')
  if re.search(r'\b(?:cpf|cnpj|matricula|matrícula|anexo|sigiloso|senha|email|nomeado|ocorreu|contratei|meu|minha|nosso|nossa)\b',value,re.I):raise ValueError('public_subject_only')
  return value.strip()
 @model_validator(mode='after')
 def nonempty(self):
  if not self.topic and not self.norms:raise ValueError('public_subject_or_norm_required')
  return self
 def public_query(self):return ' '.join([self.topic,*[n.kind+' '+str(n.number)+'/'+str(n.year) for n in self.norms]]).strip()

class RobotsRules:
 """RFC 9309 path matching, including literal query delimiters and longest rule.

 urllib.robotparser normalizes '/?' to '/', which incorrectly blocks /aimode.
 """
 def __init__(self,text):
  self.groups=[];agents=[];rules=[]
  def finish():
   if agents:self.groups.append((list(agents),list(rules)))
  for line in text.splitlines():
   line=line.split('#',1)[0].strip()
   if ':' not in line:continue
   key,value=(v.strip() for v in line.split(':',1));key=key.casefold()
   if key=='user-agent':
    if rules:finish();agents=[];rules=[]
    agents.append(value.casefold())
   elif key in {'allow','disallow'} and agents and value:rules.append((value,key=='allow'))
  finish()
 @staticmethod
 def octets(value):
  value=quote(value,safe="/?&=:$*%+[]!@,;~.-_")
  def normalize(match):
   char=chr(int(match[1],16))
   return char if char.isascii() and (char.isalnum() or char in '-._~') else '%'+match[1].upper()
  return re.sub(r'%([0-9a-fA-F]{2})',normalize,value)
 def can_fetch(self,agent,url):
  agent=agent.casefold();groups=[]
  for agents,rules in self.groups:
   scores=[0 if a=='*' else len(a) for a in agents if a=='*' or a in agent]
   if scores:groups.append((max(scores),rules))
  if not groups:return True
  best=max(score for score,_ in groups);u=urlsplit(url);path=self.octets(u.path or '/')+('?' +self.octets(u.query) if u.query else '')
  matches=[]
  for score,rules in groups:
   if score!=best:continue
   for pattern,allow in rules:
    pattern=self.octets(pattern);end=pattern.endswith('$');body=pattern[:-1] if end else pattern
    # Consecutive wildcards are equivalent to one wildcard. Leaving them as
    # repeated .* creates exponential backtracking on real LexML rules.
    body=re.sub(r'\*+','*',body)
    expression='^'+re.escape(body).replace(r'\*','.*')+('$' if end else '')
    if re.search(expression,path):matches.append((len(body.replace('*','')),allow))
  return max(matches)[1] if matches else True

def robot_policy(raw):
 text=raw.decode('utf-8',errors='replace');rules=RobotsRules(text)
 return rules,{'url':'https://www.google.com/robots.txt','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'agent':AGENT,'snapshot_gzip_base64':base64.b64encode(gzip.compress(raw,mtime=0)).decode(),'role':'provider_access_policy_not_legal_evidence'}

def candidate_url(raw,depth=0):
 try:
  if depth>2 or len(raw)>2000:return None
  u=urlsplit(raw)
  if u.scheme!='https' or u.username or u.password or u.port not in (None,443):return None
  if u.hostname in {'www.google.com','google.com'} and u.path=='/url':
   params=parse_qs(u.query);return candidate_url(next(iter(params.get('q') or params.get('url') or []),''),depth+1)
  if u.hostname not in OFFICIAL or len(raw)>2000:return None
  return urlunsplit((u.scheme,u.netloc,u.path,u.query,u.fragment))
 except (ValueError,RecursionError):return None

def search_url(topic):return 'https://www.google.com/aimode?'+urlencode({'hl':'pt-BR','q':topic+' fonte oficial'})

def network_permission(url,rules,navigation=False):
 try:
  u=urlsplit(url)
  if u.scheme!='https' or u.username or u.password or u.port not in (None,443):return False
  if u.hostname=='www.google.com':
   if navigation and u.path not in {'/aimode','/search','/'}:return False
   return rules.can_fetch(AGENT,url)
  if not navigation and u.hostname in {'www.gstatic.com','ssl.gstatic.com','fonts.gstatic.com'}:return True
 except ValueError:pass
 return False
