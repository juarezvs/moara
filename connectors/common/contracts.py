from pydantic import BaseModel, ConfigDict, Field,model_validator
from typing import Literal

KINDS = ('postgres', 'mssql', 'mysql', 'oracle', 'mongodb', 'sqlite', 'rest')
NAMES = dict(zip(KINDS, ('PostgreSQL', 'Microsoft SQL Server', 'MySQL / MariaDB', 'Oracle Database', 'MongoDB', 'SQLite', 'REST / JSON')))
METHODS = ('authorize_secp','test_connection', 'discover_catalog', 'list_schemas', 'list_objects', 'describe_object',
           'preview_data', 'execute_readonly_query', 'get_health', 'get_capabilities')

def compatible_worker_fields(kind,connection,policy):
    connection=dict(connection);policy=dict(policy)
    if kind!='postgres':
        connection.pop('postgres_readonly_mode',None)
        policy.pop('view_hashes',None)
    return connection,policy

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Connection(Strict):
    host: str = Field(default='', max_length=253)
    port: int = Field(default=0, ge=0, le=65535)
    database: str = Field(default='', max_length=128)
    username: str = Field(default='', max_length=128)
    tls: bool = True
    ca_pem: str = Field(default='', max_length=20000)
    timeout: int = Field(default=15, ge=2, le=30)
    approved_ips: list[str] = Field(default_factory=list, max_length=8)
    sqlite_id: str = Field(default='', pattern=r'^[a-f0-9-]{0,36}$')
    base_url: str = Field(default='', max_length=1000)
    endpoints: list[str] = Field(default_factory=list, max_length=30)
    query_parameters: list[str] = Field(default_factory=list, max_length=20)
    readonly_endpoints_attested: bool = False
    oracle_readonly_mode: Literal['credential','transaction'] = 'credential'
    oracle_role: str = Field(default='',pattern=r'^[A-Za-z][A-Za-z0-9_$#]{0,127}$|^$')
    oracle_schema: str = Field(default='',pattern=r'^[A-Za-z][A-Za-z0-9_$#]{0,127}$|^$')
    postgres_readonly_mode: Literal['credential','pinned_views'] = 'credential'

class Policy(Strict):
    owners: list[str] = Field(default_factory=list, max_length=100)
    groups: list[str] = Field(default_factory=list, max_length=30)
    max_rows: int = Field(default=100, ge=1, le=1000)
    timeout: int = Field(default=15, ge=2, le=30)
    allow_sensitive: bool = False
    objects: dict = Field(default_factory=dict, max_length=200)
    blocked_objects: list[str] = Field(default_factory=list, max_length=200)
    audit: Literal['masked', 'hash_only'] = 'masked'
    view_hashes: dict[str,str] = Field(default_factory=dict,max_length=200)

    @model_validator(mode='after')
    def valid_view_hashes(self):
        import re
        if any(name not in self.objects or not re.fullmatch(r'[a-f0-9]{64}',digest) for name,digest in self.view_hashes.items()):
            raise ValueError('View fingerprints must identify approved objects')
        return self

class Source(Strict):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(default='', max_length=2000)
    kind: Literal['postgres', 'mssql', 'mysql', 'oracle', 'mongodb', 'sqlite', 'rest']
    connection: Connection
    credential: dict[str, str] | None = None
    policy: Policy = Field(default_factory=Policy)
    semantic: dict = Field(default_factory=dict,max_length=40)
    active: bool = False

    @model_validator(mode='after')
    def bounded_metadata(self):
        import json
        if len(json.dumps(self.semantic,ensure_ascii=False).encode())>32000:raise ValueError('Semantic metadata exceeds 32 KB')
        return self

class Query(Strict):
    query: str | dict = Field(default='')
    object: str = Field(default='', max_length=256)
    offset: int = Field(default=0, ge=0, le=10000)
    limit: int = Field(default=50, ge=1, le=1000)

class SECPIdentity(Strict):
    username:str=Field(pattern=r'^[A-Za-z0-9._-]{1,128}$')
    organization:str=Field(pattern=r'^[A-Z][A-Z0-9-]{1,15}$')
    object_id:str=Field(pattern=r'^[a-fA-F0-9-]{36}$')
    issuer:str=Field(pattern=r'^[a-f0-9]{64}$')
    profile:str|None=Field(default=None,pattern=r'^[A-Za-z0-9_-]{1,80}$')

class WorkerCall(Strict):
    method: Literal['authorize_secp','test_connection', 'discover_catalog', 'list_schemas', 'list_objects', 'describe_object', 'preview_data', 'execute_readonly_query']
    connection: Connection
    credential: dict[str, str] = Field(default_factory=dict)
    policy: Policy = Field(default_factory=Policy)
    request: Query = Field(default_factory=Query)
    identity:SECPIdentity|None=None
