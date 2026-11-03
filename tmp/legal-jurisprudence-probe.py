import asyncio,json,time
from pathlib import Path
import httpx

async def main():
    headers={'Authorization':'Bearer '+Path('/run/secrets/moara_legal_key').read_text().strip(),
             'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'}
    async with httpx.AsyncClient(trust_env=False) as client:
        report=[]
        for number,year,article in [(13105,2015,'9'),(9868,1999,'27')]:
            start=time.monotonic()
            response=await client.post('http://localhost:8076/mcp',headers=headers,
                json={'jsonrpc':'2.0','id':number,'method':'tools/call','params':{'name':'verify_legal_sources',
                     'arguments':{'reference_date':'2026-10-30','norms':[{'kind':'LEI','number':number,'year':year,'articles':[article]}]}}},timeout=90)
            response.raise_for_status();package=response.json()['result']['structuredContent'];norm=package['norms'][0]
            assert package['legal_conclusion_allowed'] is False
            if number==13105:
                assert norm['status']=='official_text_retrieved',norm['gaps']
                assert norm['jurisprudence'],norm['gaps']
            else:assert norm['status']=='unconfirmed' and norm['gaps']
            if number==9868:assert any(c['source']=='STF' for c in norm['source_checks'])
            report.append({'norm':number,'article':article,'seconds':round(time.monotonic()-start,2),'excerpts':len(norm['excerpts']),
                'constitutional_references':len(norm['jurisprudence']), 'effects_confirmed':False,
                'source_checks':[{k:v for k,v in s.items() if k not in ('search_hits',)} for s in norm['source_checks']]})
        print(json.dumps(report,ensure_ascii=True),flush=True)

asyncio.run(main())
