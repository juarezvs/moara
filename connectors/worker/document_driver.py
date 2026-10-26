import http.client
import json
import socket
import ssl
from urllib.parse import urlsplit, urlencode
from common.policy import Rejected, pinned_ip, allowed_objects, safe_rows

def mongo(body, forbidden):
    import pymongo
    c, policy, request = body['connection'], body['policy'], body['request']
    ip = pinned_ip(c, forbidden)
    options = {'host': ip, 'port': c['port'], 'username': c['username'],
        'password': body['credential'].get('password',''), 'authSource': c['database'],
        'serverSelectionTimeoutMS': c['timeout']*1000, 'connectTimeoutMS': c['timeout']*1000,
        'socketTimeoutMS': c['timeout']*1000, 'tls': c['tls'], 'directConnection': True,
        'appname': 'Curumim-Readonly-Connector'}
    if c.get('ca_pem'):
        from pathlib import Path
        import os
        ca = '/tmp/mongo-ca-'+str(os.getpid())+'.pem'; Path(ca).write_text(c['ca_pem']); options['tlsCAFile']=ca
    else: ca=None
    if c['tls'] and c['host'] != ip: raise Rejected('MongoDB TLS exige certificado válido para o IP aprovado nesta versão')
    client = pymongo.MongoClient(**options)
    try:
        db = client[c['database']]
        status = db.command({'connectionStatus':1,'showPrivileges':True})
        privileges = status.get('authInfo',{}).get('authenticatedUserPrivileges',[])
        allowed = {'find','listCollections','listCollectionNames','listIndexes','collStats','dbStats','dbHash','killCursors','changeStream','planCacheRead','listSearchIndexes'}
        if not status.get('authInfo',{}).get('authenticatedUsers') or not privileges:
            raise Rejected('Use usuário MongoDB autenticado com privilégios verificáveis')
        for privilege in privileges:
            if set(privilege['actions'])-allowed or privilege.get('resource',{}).get('db') != c['database']:
                raise Rejected('MongoDB exige somente leitura restrita a este banco')
        if body['method']=='test_connection': return {'ok':True,'readonly_verified':True,'verification':'effective_privileges'}
        objects={}
        for item in db.list_collections():
            name=item['name']
            if name.startswith('system.') or item.get('type')!='collection':continue
            samples=list(db[name].find({},max_time_ms=c['timeout']*1000).limit(10))
            fields={}
            for sample in samples:
                for key,value in sample.items():
                    if key.startswith('$') or '.' in key:continue
                    fields[key]={'name':key,'type':type(value).__name__,'sensitive':isinstance(value,(dict,list)) or any(s in key.lower() for s in ['password','senha','token','secret','cpf','email','salario'])}
            objects[name]={'type':'collection','fields':list(fields.values()),'sampled_schema':True}
        if body['method']=='discover_catalog':return {'database':c['database'],'objects':objects,'relationships':[],'readonly_verified':True}
        if body['method']=='list_objects':return {'objects':objects}
        if body['method']=='describe_object':return objects.get(request['object'],{})
        permitted=allowed_objects(policy)
        name=request['object']
        if name not in permitted or name not in objects:raise Rejected('Coleção não autorizada')
        query=request['query'] or {}
        if body['method']=='preview_data':query={}
        if not isinstance(query,dict) or set(query)-{'filter','sort'}:raise Rejected('Use somente filter/sort; pipelines e comandos não são aceitos')
        columns=[f['name'] for f in permitted[name]['fields']]
        def validate(value,depth=0):
            if depth>5:raise Rejected('Filtro muito profundo')
            if isinstance(value,dict):
                for key,item in value.items():
                    if key.startswith('$'):
                        if key not in {'$eq','$ne','$gt','$gte','$lt','$lte','$in','$nin','$and','$or','$not','$exists'}:raise Rejected('Operador MongoDB não permitido')
                    elif key not in columns:raise Rejected('Campo não autorizado')
                    validate(item,depth+1)
            elif isinstance(value,list):
                if len(value)>50:raise Rejected('Filtro excede limite')
                for item in value:validate(item,depth+1)
            elif not isinstance(value,(str,int,float,bool,type(None))):raise Rejected('Valor inválido')
        condition=query.get('filter',{});validate(condition)
        sort=query.get('sort',{})
        if not isinstance(sort,dict) or any(k not in columns or v not in {-1,1} for k,v in sort.items()):raise Rejected('Ordenação inválida')
        limit=min(request['limit'],policy['max_rows'])
        projection={name:1 for name in columns}
        if '_id' not in columns:projection['_id']=0
        cursor=db[name].find(condition,projection,max_time_ms=min(c['timeout'],policy['timeout'])*1000).skip(request['offset']).limit(limit+1)
        if sort:cursor=cursor.sort(list(sort.items()))
        docs=list(cursor);rows=[[d.get(col) for col in columns] for d in docs]
        result=safe_rows(columns,rows,limit)
        return {**result,'objects':[name],'readonly_verified':True,'offset':request['offset'],'limit':limit,
            'next_offset':request['offset']+limit if result['incomplete'] else None}
    finally:
        client.close()
        if ca:
            from pathlib import Path
            Path(ca).unlink(missing_ok=True)

def rest(body, forbidden):
    c,request,policy=body['connection'],body['request'],body['policy']
    parsed=urlsplit(c['base_url'])
    if parsed.scheme not in {'https','http'} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'','/'}:
        raise Rejected('Use uma origem HTTP(S) sem credenciais, caminho ou parâmetros')
    if not c['readonly_endpoints_attested'] or body['credential'].get('readonly_token_attested')!='true':
        raise Rejected('Confirme endpoints sem efeitos colaterais e credencial externa somente de leitura')
    if parsed.hostname!=c['host'] or (parsed.port or (443 if parsed.scheme=='https' else 80))!=c['port'] or (parsed.scheme=='https')!=c['tls']:
        raise Rejected('Origem e configuração TLS divergentes')
    ip=pinned_ip(c,forbidden)
    endpoints=c['endpoints']
    if not endpoints or any(not p.startswith('/') or p.startswith('//') or any(x in p for x in ['?','#','%','..','\\','\r','\n']) for p in endpoints):
        raise Rejected('Endpoints exatos inválidos')
    if body['method']=='list_schemas':raise Rejected('REST não possui schemas')
    path=request['object'] or endpoints[0]
    if path not in endpoints:raise Rejected('Endpoint não autorizado')
    query=request['query'] or {}
    if not isinstance(query,dict) or set(query)-{'method','params'}:raise Rejected('Consulta REST inválida')
    method=query.get('method','GET')
    params=query.get('params',{})
    if method not in {'GET','HEAD'} or not isinstance(params,dict) or set(params)-set(c['query_parameters']):raise Rejected('Método ou parâmetros não autorizados')
    if any(not isinstance(v,(str,int,float,bool)) or len(str(v))>200 for v in params.values()):raise Rejected('Parâmetro inválido')
    if body['method'] not in {'test_connection','discover_catalog','list_objects','describe_object'} and path not in allowed_objects(policy):
        raise Rejected('Endpoint fora da política')
    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            self.sock=socket.create_connection((ip,self.port),self.timeout)
            self.sock=self._context.wrap_socket(self.sock,server_hostname=self.host)
    if c['tls']:
        context=ssl.create_default_context(cadata=c.get('ca_pem') or None)
        conn=PinnedHTTPS(c['host'],c['port'],timeout=c['timeout'],context=context)
    else:conn=http.client.HTTPConnection(ip,c['port'],timeout=c['timeout'])
    headers={'Accept':'application/json','Host':parsed.netloc}
    if body['credential'].get('token'):headers['Authorization']='Bearer '+body['credential']['token']
    try:
        conn.request(method,path+('?' + urlencode(params) if params else ''),headers=headers)
        response=conn.getresponse()
        if response.status!=200:raise Rejected('Endpoint indisponível; redirecionamentos e outras respostas são recusados')
        if method=='HEAD':return {'ok':True,'status':200,'readonly_verified':True,'verification':'administrator_and_api_owner_attestation'}
        if 'application/json' not in response.getheader('Content-Type',''):raise Rejected('Endpoint deve retornar JSON')
        raw=response.read(1000001)
        if len(raw)>1000000:raise Rejected('Resposta REST excede 1 MB; configure paginação na API de origem')
        data=json.loads(raw)
    finally:conn.close()
    if body['method']=='test_connection':return {'ok':True,'readonly_verified':True,'verification':'administrator_and_api_owner_attestation'}
    records=data if isinstance(data,list) else data.get('data',data.get('items',[data])) if isinstance(data,dict) else []
    if not isinstance(records,list) or any(not isinstance(x,dict) for x in records):raise Rejected('JSON deve conter objetos em lista, data ou items')
    fields={}
    for row in records[:10]:
        for key,value in row.items():
            fields[key]={'name':key,'type':type(value).__name__,'sensitive':isinstance(value,(dict,list)) or any(s in key.lower() for s in ['password','senha','token','secret','cpf','email','salario'])}
    if body['method'] in {'discover_catalog','list_objects','describe_object'}:
        # Every endpoint is independently fetched during discovery; no invented schema.
        return {'objects':{path:{'type':'endpoint','fields':list(fields.values()),'sampled_schema':True}},'relationships':[],'readonly_verified':True}
    columns=[f['name'] for f in allowed_objects(policy)[path]['fields']]
    limit=min(request['limit'],policy['max_rows']);offset=request['offset']
    rows=[[r.get(col) for col in columns] for r in records[offset:offset+limit+1]]
    result=safe_rows(columns,rows,limit)
    return {**result,'objects':[path],'readonly_verified':True,'offset':offset,'limit':limit,
        'next_offset':offset+limit if result['incomplete'] else None}
