"""Encrypted, online preservation and isolated restoration before Moara migration.

Does not stop chat or alter existing volumes. SQLite uses its online backup API;
PostgreSQL counts and dump share one exported, read-only repeatable-read snapshot.
Each service has its own snapshot time; this is not a distributed transaction.
"""
import argparse
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT=Path(os.environ.get('MOARA_PRESERVATION_ROOT',Path(__file__).resolve().parents[3])).resolve()
os.umask(0o077)
KEY=ROOT/'secrets/backup_key'
ENV=dict(line.split('=',1) for line in (ROOT/'infrastructure/.env').read_text().splitlines() if '=' in line)
VOLUMES={'webui':'ai-server_webui','studio':'ai-server_studio_data','caddy':'ai-server_caddy_data',
         'moara':'ai-server_moara_data','connector_sqlite':'ai-server_connector_sqlite','grafana':'ai-server_moara_grafana'}

def run(args,**kwargs):
    if kwargs.pop('capture_output',False):kwargs.setdefault('stdout',subprocess.PIPE)
    kwargs.setdefault('stderr',subprocess.PIPE)
    result=subprocess.run(args,**kwargs)
    if result.returncode:
        diagnostic=result.stderr or b''
        if isinstance(diagnostic,str):diagnostic=diagnostic.encode()
        (ROOT/'secrets/moara-preservation-error.log').write_bytes(diagnostic)
        raise RuntimeError('Preservation command failed: '+Path(args[0]).name)
    return result

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()

def authenticate(path):
    digest=hmac.new(hashlib.sha256(b'moara-preservation:'+KEY.read_bytes()).digest(),digestmod=hashlib.sha256)
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()

SNAPSHOT=r'''
import hashlib,json,os,re,shutil,sqlite3,sys
from pathlib import Path
source=Path('/source');target=Path('/snapshot')
runtime_links={}
for link in source.rglob('*'):
 if link.is_symlink():
  relative=link.relative_to(source)
  # The renderer creates this exact link to its immutable JS toolchain. Record
  # the dependency without traversing it or putting an unsafe link in the tar.
  if len(relative.parts)==2 and re.fullmatch(r'[a-f0-9-]{36}',relative.parts[0]) and relative.parts[1]=='node_modules' and os.readlink(link)=='/opt/studio-js/node_modules':
   runtime_links[str(relative)]='/opt/studio-js/node_modules';continue
  if not link.resolve().is_relative_to(source) or not link.is_file():raise RuntimeError('External or directory symbolic link requires review')
def files():return sorted(p for p in source.rglob('*') if p.is_file() and not p.name.endswith(('-wal','-shm','-journal')))
initial=files();report={'files':{},'sqlite':{},'runtime_links':runtime_links}
for path in initial:
 relative=path.relative_to(source);dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
 with path.open('rb') as f:header=f.read(16)
 if header==bytes.fromhex('53514c69746520666f726d6174203300'):
  src=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=20)
  dst=sqlite3.connect(dest);src.backup(dst,pages=512,sleep=.01)
  assert dst.execute('PRAGMA quick_check').fetchone()[0]=='ok'
  tables=[r[0] for r in dst.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
  counts={name:dst.execute('SELECT count(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
  report['sqlite'][str(relative)]={'integrity':'ok','row_counts':counts}
  dst.close();src.close()
 else:
  before=path.stat();shutil.copy2(path,dest);after=path.stat()
  if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('File changed during preservation')
 digest=hashlib.sha256()
 with dest.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):digest.update(block)
 report['files'][str(relative)]={'sha256':digest.hexdigest(),'bytes':dest.stat().st_size,'internal_symlink_materialized':path.is_symlink()}
if [str(p.relative_to(source)) for p in initial]!=[str(p.relative_to(source)) for p in files()]:raise RuntimeError('File set changed during preservation')
print(json.dumps(report))
'''

def quote(value):return '"'+value.replace('"','""')+'"'

def pg_counts(container):
    def sql(query):
        return run(['docker','exec',container,'psql','-U','postgres','-d','ai','-qAt','-v','ON_ERROR_STOP=1','-c',query],capture_output=True,text=True).stdout.strip()
    tables=json.loads(sql("SELECT coalesce(json_agg(json_build_array(schemaname,tablename)),'[]') FROM pg_tables WHERE schemaname NOT LIKE 'pg_%' AND schemaname <> 'information_schema'"))
    return {schema+'.'+table:int(sql('SELECT count(*) FROM '+quote(schema)+'.'+quote(table))) for schema,table in tables}

def postgres_snapshot(stage):
    process=subprocess.Popen(['docker','exec','-i','ai-server-postgres-1','psql','-U','postgres','-d','ai','-qAt','-v','ON_ERROR_STOP=1'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def sql(query):
        process.stdin.write(query+';\n');process.stdin.flush()
        line=process.stdout.readline().strip()
        if process.poll() is not None:raise RuntimeError('Read-only PostgreSQL snapshot session failed')
        return line
    try:
        process.stdin.write('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n');process.stdin.flush()
        snapshot=sql('SELECT pg_export_snapshot()')
        if not re.fullmatch(r'[0-9A-Fa-f]+-[0-9A-Fa-f]+-\d+',snapshot):raise RuntimeError('Unexpected snapshot identifier')
        tables=json.loads(sql("SELECT coalesce(json_agg(json_build_array(schemaname,tablename)),'[]') FROM pg_tables WHERE schemaname NOT LIKE 'pg_%' AND schemaname <> 'information_schema'"))
        counts={schema+'.'+table:int(sql('SELECT count(*) FROM '+quote(schema)+'.'+quote(table))) for schema,table in tables}
        with (stage/'postgres.dump').open('wb') as stream:
            run(['docker','exec','ai-server-postgres-1','pg_dump','-U','postgres','-d','ai','-Fc','--no-owner','--no-acl','--snapshot='+snapshot],stdout=stream)
        return counts
    finally:
        if process.poll() is None:
            process.stdin.write('ROLLBACK;\n\\q\n');process.stdin.flush()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()

def backup():
    assert KEY.is_file(),'Existing protected backup key required'
    KEY.chmod(0o600)
    target=ROOT/'backups'/('moara-before-migration-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.tar.enc')
    manifest={'format':'moara-online-v1','created':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'postgres_image':ENV['POSTGRES_IMAGE'],'python_image':ENV['PYTHON_IMAGE'],'volumes':{},
        'chat_stopped':False,'weights_included':False,'verified':False}
    with tempfile.TemporaryDirectory(prefix='moara-preserve-',dir=ROOT/'backups') as temp:
        stage=Path(temp)
        print('PRESERVATION_POSTGRES_SNAPSHOT',flush=True)
        manifest['postgres_counts']=postgres_snapshot(stage)
        manifest['postgres_sha256']=sha(stage/'postgres.dump')
        for label,volume in VOLUMES.items():
            print('PRESERVATION_VOLUME',label,flush=True)
            dest=stage/'volumes'/label;dest.mkdir(parents=True)
            result=run(['docker','run','--rm','--pull=never','-i','--network','none','--read-only','--memory','768m','--cpus','2',
                '--security-opt','no-new-privileges:true','--cap-drop','ALL','--cap-add','DAC_READ_SEARCH','--tmpfs','/tmp:size=64m,mode=1777',
                '--mount',f'type=volume,src={volume},dst=/source,readonly',
                '--mount',f'type=bind,src={dest},dst=/snapshot',ENV['PYTHON_IMAGE'],'python','-c',SNAPSHOT],capture_output=True,text=True)
            manifest['volumes'][label]=json.loads(result.stdout)
        print('PRESERVATION_CONFIG_SNAPSHOT',flush=True)
        config=stage/'config';config.mkdir(mode=0o700)
        config_code=Path(__file__).with_name('config_snapshot.py').read_text()
        result=run(['docker','run','--rm','--pull=never','--network','none','--read-only','--memory','768m','--cpus','2',
            '--security-opt','no-new-privileges:true','--cap-drop','ALL','--cap-add','DAC_READ_SEARCH',
            '--tmpfs','/tmp:size=64m,mode=1777',
            '--mount',f'type=bind,src={ROOT},dst=/source,readonly',
            '--mount',f'type=bind,src={config},dst=/snapshot',ENV['PYTHON_IMAGE'],'python','-c',config_code],capture_output=True,text=True)
        manifest['config_snapshot']=json.loads(result.stdout)
        (stage/'manifest.json').write_text(json.dumps(manifest,indent=2))
        archive=stage/'preservation.tar.gz'
        with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
            tar.add(stage/'manifest.json',arcname='manifest.json');tar.add(stage/'postgres.dump',arcname='postgres.dump')
            tar.add(stage/'volumes',arcname='volumes')
            tar.add(config,arcname='config')
        run(['openssl','enc','-aes-256-cbc','-pbkdf2','-iter','200000','-salt','-in',str(archive),'-out',str(target),'-pass','file:'+str(KEY)])
    target.with_suffix('.enc.hmac').write_text(authenticate(target))
    public={'file':target.name,'sha256':sha(target),'encrypted_bytes':target.stat().st_size,'chat_stopped':False,
        'postgres_tables':len(manifest['postgres_counts']),'volumes':{k:{'files':len(v['files']),'sqlite_databases':len(v['sqlite']),
        'runtime_toolchain_links':len(v.get('runtime_links',{}))} for k,v in manifest['volumes'].items()},'verified':False}
    target.with_suffix('.enc.manifest.json').write_text(json.dumps(public,indent=2))
    (ROOT/'docs/runtime/moara-preservation-latest.json').write_text(json.dumps(public,indent=2))
    print(json.dumps(public),flush=True)
    return target

def verify(path):
    path=path.resolve(strict=True)
    if path.parent!=(ROOT/'backups').resolve() or not path.name.startswith('moara-before-migration-'):raise ValueError('Expected migration preservation file in backups')
    expected=path.with_suffix('.enc.hmac').read_text().strip()
    if not hmac.compare_digest(expected,authenticate(path)):raise ValueError('Backup authentication failed; not decrypted')
    nonce=secrets.token_hex(8);name='moara-restore-'+nonce;volume=name+'-pg';created_container=False;created_volume=False
    result={'backup':path.name,'verified':False,'production_modified':False,'network':'none'}
    try:
        with tempfile.TemporaryDirectory(prefix='moara-verify-',dir=ROOT/'backups') as temp:
            stage=Path(temp);archive=stage/'preservation.tar.gz'
            run(['openssl','enc','-d','-aes-256-cbc','-pbkdf2','-iter','200000','-in',str(path),'-out',str(archive),'-pass','file:'+str(KEY)])
            with tarfile.open(archive) as tar:tar.extractall(stage,filter='data')
            manifest=json.loads((stage/'manifest.json').read_text());assert manifest['format']=='moara-online-v1'
            assert sha(stage/'postgres.dump')==manifest['postgres_sha256']
            for filename,meta in manifest.get('config_snapshot',{}).get('files',{}).items():
                if sha(stage/'config'/filename)!=meta['sha256']:raise ValueError('Restored configuration hash mismatch')
            import sqlite3
            for label,details in manifest['volumes'].items():
                for filename,target in details.get('runtime_links',{}).items():
                    assert re.fullmatch(r'[a-f0-9-]{36}/node_modules',filename) and target=='/opt/studio-js/node_modules'
                    assert not (stage/'volumes'/label/filename).exists(),'External runtime link must remain metadata only'
                for filename,meta in details['files'].items():assert sha(stage/'volumes'/label/filename)==meta['sha256']
                for filename,meta in details['sqlite'].items():
                    db=sqlite3.connect((stage/'volumes'/label/filename).as_uri()+'?mode=ro',uri=True)
                    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                    for table,count in meta['row_counts'].items():assert db.execute('SELECT count(*) FROM '+quote(table)).fetchone()[0]==count
                    db.close()
            assert (stage/'volumes/caddy/caddy/pki/authorities/local/root.crt').read_text().startswith('-----BEGIN CERTIFICATE-----')
            run(['docker','volume','create','--label','moara.restore='+nonce,volume],stdout=subprocess.DEVNULL);created_volume=True
            run(['docker','run','-d','--pull=never','--name',name,'--label','moara.restore='+nonce,'--network','none','--memory','2g',
                '--security-opt','no-new-privileges:true','--mount',f'type=volume,src={volume},dst=/var/lib/postgresql/data',
                '--mount',f'type=bind,src={stage}/config/secrets/postgres_password,dst=/run/db-password,readonly',
                '-e','POSTGRES_PASSWORD_FILE=/run/db-password','-e','POSTGRES_DB=ai',manifest['postgres_image']],stdout=subprocess.DEVNULL);created_container=True
            for _ in range(90):
                if subprocess.run(['docker','exec',name,'pg_isready','-U','postgres','-d','ai'],capture_output=True).returncode==0:break
                time.sleep(1)
            else:raise RuntimeError('Isolated restore database did not become ready')
            print('PRESERVATION_RESTORE_POSTGRES',flush=True)
            with (stage/'postgres.dump').open('rb') as stream:
                run(['docker','exec','-i',name,'pg_restore','--exit-on-error','--no-owner','--no-acl','-U','postgres','-d','ai'],stdin=stream)
            assert pg_counts(name)==manifest['postgres_counts'],'Restored table counts differ'
            result.update(verified=True,postgres_restored=True,postgres_table_counts_matched=True,all_file_hashes_matched=True,configuration_hashes_matched=bool(manifest.get('config_snapshot')),
                all_sqlite_integrity_and_counts_matched=True,ca_restored=True,runtime_toolchain_links_verified=True,
                verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    finally:
        if created_container:
            info=json.loads(run(['docker','inspect',name],capture_output=True,text=True).stdout)[0]
            assert info['Config']['Labels'].get('moara.restore')==nonce
            run(['docker','rm','-f',name],stdout=subprocess.DEVNULL)
        if created_volume:
            info=json.loads(run(['docker','volume','inspect',volume],capture_output=True,text=True).stdout)[0]
            assert info['Labels'].get('moara.restore')==nonce
            run(['docker','volume','rm',volume],stdout=subprocess.DEVNULL)
        path.with_suffix('.enc.restore.json').write_text(json.dumps(result,indent=2))
        (ROOT/'docs/runtime/moara-preservation-restore.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    if result['verified']:
        public_path=path.with_suffix('.enc.manifest.json')
        public=json.loads(public_path.read_text())
        if sha(path)!=public['sha256']:raise ValueError('Preservation artifact changed after verification')
        public.update(verified=True,verified_at=result['verified_at'])
        public_path.write_text(json.dumps(public,indent=2))
        (ROOT/'docs/runtime/moara-preservation-latest.json').write_text(json.dumps(public,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['backup','verify','backup-and-verify']);parser.add_argument('path',nargs='?')
    args=parser.parse_args()
    if args.action=='verify':verify(Path(args.path))
    else:
        target=backup()
        if args.action=='backup-and-verify':verify(target)
