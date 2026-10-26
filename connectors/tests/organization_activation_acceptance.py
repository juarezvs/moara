"""Hub authorization with deliberately mocked directory HTTP and database rows.

Run inside the installed hub image. No production DB write or Oracle call occurs.
"""
import asyncio
import json
import uuid
import httpx
from fastapi import HTTPException
import main

async def test():
    row={'id':str(uuid.uuid4()),'semantic':{'organization':'QA'},'active':True,'verified':True,'policy':{'objects':{}}}
    state={'enabled':True,'status':200};checks={}
    async def sql(*args,**kwargs):return row
    original_sql=main.store.sql;original_http=main.HTTP
    main.store.sql=sql
    def upstream(request):return httpx.Response(state['status'],json={'enabled':state['enabled']})
    user={'owner':'key:synthetic-unit-qa','admin':True,'allowed_sources':None}
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        main.HTTP=client
        try:
            checks['active_unit_allowed']=bool(await main.organization_active(row))
            state['enabled']=False
            checks['inactive_unit_denied']=not await main.organization_active(row)
            try:await main.source(row['id'],user,active=True)
            except HTTPException as error:checks['even_admin_cannot_query_inactive_unit']=error.status_code==403
            try:await main.activate(row['id'],main.Activation(active=True),user)
            except HTTPException as error:checks['inactive_unit_cannot_activate_source']=error.status_code==403
            state['status']=503
            checks['directory_outage_fails_closed']=not await main.organization_active(row)
            row['semantic']['organization']='QA/../../invalid'
            checks['invalid_unit_path_denied']=not await main.organization_active(row)
            row['semantic']={}
            checks['existing_unbound_sources_preserved']=await main.organization_active(row)
        finally:main.store.sql=original_sql;main.HTTP=original_http
    assert len(checks)==7 and all(checks.values())
    print(json.dumps({'passed':True,'checks':checks,'scope':'Real hub authorization functions; directory HTTP and source metadata deliberately mocked; no production writes'}))
asyncio.run(test())
