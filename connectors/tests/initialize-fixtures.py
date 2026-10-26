"""Writes ONLY to labeled disposable fixture containers, never to registered sources."""
import json
import subprocess
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
creds=json.loads((ROOT/'secrets/connector_fixture_credentials.json').read_text())

def initialize(kind,driver,code):
    item=json.loads(subprocess.check_output(['docker','inspect','cc-fixture-'+kind]))[0]
    assert item['Config']['Labels'].get('curumim.fixtures')=='true'
    assert item['Config']['Labels'].get('com.docker.compose.project')=='cc-fixtures'
    assert not item['HostConfig'].get('PortBindings')
    program='import json,sys\np=json.load(sys.stdin)\n'+code
    for attempt in range(90):
        result=subprocess.run(['docker','exec','-i','ai-server-connector-'+driver+'-1','python','-c',program],input=json.dumps(creds),text=True,capture_output=True)
        if result.returncode==0:
            print('FIXTURE_INITIALIZED',kind,flush=True);return
        if attempt in {0,15,30,60}:print('WAIT_FIXTURE',kind,type(result).__name__,flush=True)
        time.sleep(2)
    # SQL inputs containing passwords are never printed, even on fixture failures.
    (ROOT/('secrets/fixture-'+kind+'-error.txt')).write_text(result.stderr)
    raise RuntimeError('Fixture initialization failed: '+kind+'; private diagnostic file saved')

initialize('pg','postgres',r'''
import psycopg
db=psycopg.connect(host='cc-fixture-pg',user='postgres',password=p['admin_password'],dbname='postgres',connect_timeout=3,autocommit=True)
if not db.execute("SELECT 1 FROM pg_roles WHERE rolname='cc_reader'").fetchone():
 db.execute(psycopg.sql.SQL('CREATE ROLE cc_reader LOGIN PASSWORD {}').format(psycopg.sql.Literal(p['reader_password'])))
for name,table in [('cc_ponto','ponto'),('cc_cadastro','people')]:
 if not db.execute('SELECT 1 FROM pg_database WHERE datname=%s',(name,)).fetchone():db.execute('CREATE DATABASE '+name)
 conn=psycopg.connect(host='cc-fixture-pg',user='postgres',password=p['admin_password'],dbname=name,autocommit=True)
 conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC');conn.execute('CREATE SCHEMA IF NOT EXISTS app')
 conn.execute('CREATE TABLE IF NOT EXISTS app.'+table+'(id integer PRIMARY KEY,nome text,saldo_minutos integer,email text)')
 conn.execute('TRUNCATE app.'+table)
 for row in [(1,'Ana Sintetica',120,'ana@example.invalid'),(2,'Beto Sintetico',90,'beto@example.invalid'),(3,'Cris Sintetica',0,'cris@example.invalid')]:
  conn.execute('INSERT INTO app.'+table+' VALUES(%s,%s,%s,%s)',row)
 conn.execute('CREATE OR REPLACE VIEW app.v_'+table+' AS SELECT id,nome,saldo_minutos FROM app.'+table)
 conn.execute('GRANT USAGE ON SCHEMA app TO cc_reader');conn.execute('GRANT SELECT ON ALL TABLES IN SCHEMA app TO cc_reader')
 conn.execute('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC');conn.close()
db.close()
''')
for kind in ['mysql','mariadb']:
 initialize(kind,'mysql',r'''
import pymysql
db=pymysql.connect(host='cc-fixture-'''+kind+r'''',user='root',password=p['admin_password'],connect_timeout=3,autocommit=True)
with db.cursor() as cur:
 cur.execute('CREATE DATABASE IF NOT EXISTS rh');cur.execute('USE rh')
 cur.execute('CREATE TABLE IF NOT EXISTS employees(id integer PRIMARY KEY,nome varchar(100),saldo_minutos integer,email varchar(100))')
 cur.execute('TRUNCATE employees')
 cur.executemany('INSERT INTO employees VALUES(%s,%s,%s,%s)',[(1,'Ana Sintetica',120,'ana@example.invalid'),(2,'Beto Sintetico',60,'beto@example.invalid'),(3,'Cris Sintetica',0,'cris@example.invalid')])
 cur.execute('CREATE OR REPLACE VIEW v_employees AS SELECT id,nome,saldo_minutos FROM employees')
 cur.execute("CREATE USER IF NOT EXISTS 'cc_reader'@'%%' IDENTIFIED BY %s",(p['reader_password'],))
 cur.execute("GRANT SELECT, SHOW VIEW ON rh.* TO 'cc_reader'@'%'")
db.close()
''')
initialize('mssql','mssql',r'''
import pyodbc
db=pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=cc-fixture-mssql,1433;UID=sa;PWD={'+p['admin_password']+'};Encrypt=no;TrustServerCertificate=yes',timeout=3,autocommit=True)
cur=db.cursor();cur.execute("IF DB_ID('cc_hr') IS NULL CREATE DATABASE cc_hr");cur.execute('USE cc_hr')
cur.execute("IF SCHEMA_ID('app') IS NULL EXEC('CREATE SCHEMA app')")
cur.execute("IF OBJECT_ID('app.employees') IS NULL CREATE TABLE app.employees(id integer PRIMARY KEY,nome varchar(100),saldo_minutos integer,email varchar(100))")
cur.execute('TRUNCATE TABLE app.employees')
for row in [(1,'Ana Sintetica',120,'ana@example.invalid'),(2,'Beto Sintetico',60,'beto@example.invalid'),(3,'Cris Sintetica',0,'cris@example.invalid')]:cur.execute('INSERT INTO app.employees VALUES(?,?,?,?)',row)
cur.execute("IF SUSER_ID('cc_reader') IS NULL CREATE LOGIN cc_reader WITH PASSWORD='"+p['reader_password']+"'")
cur.execute("IF USER_ID('cc_reader') IS NULL CREATE USER cc_reader FOR LOGIN cc_reader")
cur.execute('GRANT SELECT ON SCHEMA::app TO cc_reader');cur.execute('GRANT VIEW DEFINITION TO cc_reader')
cur.execute('DENY INSERT, UPDATE, DELETE, EXECUTE, ALTER TO cc_reader')
db.close()
''')
initialize('oracle','oracle',r'''
import oracledb
db=oracledb.connect(user='system',password=p['admin_password'],host='cc-fixture-oracle',port=1521,service_name='FREEPDB1',tcp_connect_timeout=3)
cur=db.cursor()
for name in ['CC_DATA','CC_READER']:
 try:cur.execute('CREATE USER '+name+' IDENTIFIED BY "'+p['reader_password']+'" DEFAULT TABLESPACE USERS QUOTA 20M ON USERS')
 except oracledb.DatabaseError as exc:
  if exc.args[0].code!=1920:raise
cur.execute('GRANT CREATE SESSION TO CC_READER')
try:cur.execute('CREATE TABLE CC_DATA.EMPLOYEES(ID NUMBER PRIMARY KEY,NOME VARCHAR2(100),SALDO_MINUTOS NUMBER,EMAIL VARCHAR2(100))')
except oracledb.DatabaseError as exc:
 if exc.args[0].code!=955:raise
cur.execute('TRUNCATE TABLE CC_DATA.EMPLOYEES')
cur.executemany('INSERT INTO CC_DATA.EMPLOYEES VALUES(:1,:2,:3,:4)',[(1,'Ana Sintetica',120,'ana@example.invalid'),(2,'Beto Sintetico',60,'beto@example.invalid'),(3,'Cris Sintetica',0,'cris@example.invalid')]);db.commit()
cur.execute('GRANT SELECT ON CC_DATA.EMPLOYEES TO CC_READER');db.close()
''')
initialize('mongodb','mongodb',r'''
from pymongo import MongoClient
client=MongoClient('cc-fixture-mongodb',username='root',password=p['admin_password'],authSource='admin',serverSelectionTimeoutMS=3000)
db=client.cc_docs;db.employees.delete_many({})
db.employees.insert_many([{'id':1,'nome':'Ana Sintetica','saldo_minutos':120,'email':'ana@example.invalid'},{'id':2,'nome':'Beto Sintetico','saldo_minutos':60,'email':'beto@example.invalid'},{'id':3,'nome':'Cris Sintetica','saldo_minutos':0,'email':'cris@example.invalid'}])
try:db.command('createUser','cc_reader',pwd=p['reader_password'],roles=[{'role':'read','db':'cc_docs'}])
except Exception as exc:
 if getattr(exc,'code',None)!=51003:raise
client.close()
''')
print('ALL_FIXTURES_INITIALIZED',flush=True)
