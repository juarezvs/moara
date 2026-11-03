import asyncio,json,time
import httpx
from moara.legal_mcp.contracts import Verification
from moara.legal_mcp.sources import verify

async def main():
    async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as client:
        start=time.monotonic()
        value=await verify(client,Verification.model_validate({'reference_date':'2020-01-01','norms':[
            {'kind':'LEI','number':13105,'year':2015,'articles':['12']}]}))
        print(json.dumps({'seconds':round(time.monotonic()-start,2),'status':value['status'],
          'norms':[{k:v for k,v in n.items() if k not in ('snapshots','changes','publication','notes')} for n in value['norms']],
          'snapshots':[{k:v for k,v in s.items() if k!='snapshot_gzip_base64'} for n in value['norms'] for s in n['snapshots']]},ensure_ascii=False),flush=True)

asyncio.run(main())
