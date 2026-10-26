import base64
import hashlib
import os
from dataclasses import dataclass,field
from pathlib import Path
from sqlalchemy.engine import URL
from cryptography.fernet import Fernet

def secret(name):
    value=(Path(os.getenv('MOARA_SECRETS_DIR','/run/secrets'))/name).read_text().strip()
    if len(value)<32:raise RuntimeError('Required protected secret is missing or invalid')
    return value

def database_url(kind='runtime'):
    roles={'runtime':('moara_app','moara_db_password'),'migration':('moara_migrator','moara_migration_password'),
        'worker':('moara_worker','moara_worker_password')}
    user,filename=roles[kind]
    return URL.create('postgresql+psycopg',username=user,password=secret(filename),host=os.getenv('MOARA_DB_HOST','postgres'),database=os.getenv('MOARA_DB_NAME','ai'))

@dataclass(repr=False)
class Settings:
    db_url:URL
    session_key:bytes=field(repr=False)
    crypto_key:bytes=field(repr=False)
    redis_password:str=field(repr=False)
    llm_key:str=field(repr=False)
    connector_key:str=field(repr=False)
    forward_key:str=field(repr=False)
    legacy_webui:str='http://webui:8080'
    legacy_gateway:str='http://gateway:8000'
    connector_hub:str='http://connector-hub:8070'
    redis_host:str='moara-redis'
    origins:tuple=('https://localhost:8443','https://127.0.0.1:8443','https://moara.am.trf1.gov.br')
    directory_enforcement:bool=False
    session_seconds:int=28800
    session_cookie:str='__Secure-moara_session'
    version:str='1.0.0'
    metrics_key:str=field(default='',repr=False)

    @classmethod
    def load(cls):
        return cls(db_url=database_url(),directory_enforcement=os.getenv('MOARA_DIRECTORY_ENFORCEMENT','true').lower()=='true',
            session_key=secret('moara_session_key').encode(),crypto_key=secret('moara_crypto_key').encode(),
            redis_password=secret('moara_redis_password'),llm_key=secret('moara_llm_key'),connector_key=secret('connector_hub_key'),
            forward_key=secret('moara_forward_jwt_secret'),metrics_key=secret('moara_metrics_key') if (Path(os.getenv('MOARA_SECRETS_DIR','/run/secrets'))/'moara_metrics_key').is_file() else '')

    def fernet(self):return Fernet(base64.urlsafe_b64encode(hashlib.sha256(self.crypto_key).digest()))

    def redis_url(self,db=0):
        # Random hex credentials contain no URL metacharacters. Do not log this URL.
        return f'redis://:{self.redis_password}@{self.redis_host}:6379/{db}'
