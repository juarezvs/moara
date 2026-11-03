"""Native chat progress transport; fixed labels describe application work only."""
import asyncio
import contextlib
import json
import logging
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

LABELS={
    'searching_web':'Pesquisando na web com o buscador privado…',
    'checking_web_content':'Lendo as páginas e conferindo os trechos recuperados…',
    'analyzing_request':'Analisando a solicitação…',
    'preparing_legal_check':'Preparando a conferência jurídica…',
    'checking_legal_sources':'Consultando fontes oficiais de legislação…',
    'checking_precedents':'Pesquisando jurisprudência e conferindo os registros do tribunal…',
    'recovering_legal_sources':'Ampliando a pesquisa e buscando referências para localizar fontes oficiais…',
    'retrieving_documents':'Buscando trechos nos documentos selecionados…',
    'querying_data':'Consultando dados autorizados…',
    'generating_response':'Aguardando o modelo e gerando a resposta…',
    'checking_response':'Conferindo a resposta e suas referências…',
}

def publish(request,stage):
    callback=getattr(request,'scope',{}).get('_moara_chat_progress')
    if callback and stage in LABELS:callback(stage)

def event(value):return 'data: '+json.dumps(value,ensure_ascii=False)+'\n\n'

def with_progress(request,operation):
    """Start headers before RAG/legal/model waits, retaining backpressure and cancellation."""
    async def stream():
        queue=asyncio.Queue(maxsize=32)
        def progress(stage):
            # Progress never displaces content or blocks an application operation.
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event({'moara_progress':{'stage':stage,'label':LABELS[stage]}}))
        request.scope['_moara_chat_progress']=progress
        async def produce():
            try:
                result=await operation()
                if not isinstance(result,StreamingResponse):raise RuntimeError('Native chat requires an SSE response')
                async with contextlib.aclosing(result.body_iterator) as content:
                    async for chunk in content:await queue.put(chunk)
            except asyncio.CancelledError:raise
            except HTTPException as exc:
                code=exc.detail if isinstance(exc.detail,str) else 'internal_error'
                await queue.put(event({'error':{'status':exc.status_code,'code':code,'message':'Não foi possível concluir esta solicitação.'}}))
            except Exception:
                logging.getLogger(__name__).exception('Native chat operation failed')
                await queue.put(event({'error':{'status':500,'code':'internal_error','message':'Não foi possível concluir esta solicitação.'}}))
            finally:
                if not asyncio.current_task().cancelling():await queue.put(None)
        task=asyncio.create_task(produce())
        try:
            while True:
                try:chunk=await asyncio.wait_for(queue.get(),timeout=15)
                except TimeoutError:
                    yield ': keep-alive\n\n';continue
                if chunk is None:break
                yield chunk
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await task
            request.scope.pop('_moara_chat_progress',None)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no','Cache-Control':'no-store'})
