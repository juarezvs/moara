"""Measured per-file progress and bounded retries for the local embedding gateway."""
import asyncio, contextvars, functools, logging, math, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
import aiohttp

CURRENT_FILE = contextvars.ContextVar('moara_embedding_file', default=None)
RETRY_ATTEMPTS = 6
RETRY_SECONDS = 900
log = logging.getLogger(__name__)

async def publish_progress(file_id, stage, completed=0, total=0, retry_after=None):
    if not file_id:
        return
    from open_webui.models.files import Files
    progress = {'stage':stage,'completed_chunks':completed,'total_chunks':total,
        'percent':min(100,math.floor(100*completed/total)) if total else None,
        'updated_at':time.time()}
    if retry_after is not None:
        progress['retry_after_seconds']=retry_after
    result = await Files.update_file_data_by_id(file_id, {'moara_progress':progress})
    if result is None:
        log.warning('moara_file_progress_update_unavailable')

async def embed_with_progress(operation, texts, file_id=None, batch_size=16, **kwargs):
    total=len(texts);done=0;vectors=[];batch_size=max(1,min(16,int(batch_size)))
    await publish_progress(file_id,'indexing',done,total)
    for start in range(0,total,batch_size):
        batch=texts[start:start+batch_size]
        token=CURRENT_FILE.set((file_id,done,total))
        try:
            result=await operation(batch,**kwargs)
        finally:
            CURRENT_FILE.reset(token)
        if result is None or len(result)!=len(batch):
            raise ValueError('embedding_batch_incomplete')
        vectors.extend(result);done+=len(batch)
        await publish_progress(file_id,'indexing',done,total)
    await publish_progress(file_id,'saving',done,total)
    return vectors

def retry_delay(headers,attempt):
    delay=min(60,2**(attempt+1));raw=(headers or {}).get('Retry-After')
    if raw is not None:
        try:value=float(raw)
        except (ValueError,TypeError):
            try:value=(parsedate_to_datetime(raw)-datetime.now(timezone.utc)).total_seconds()
            except (ValueError,TypeError,OverflowError):value=0
        if math.isfinite(value):
            delay=max(delay,max(0,value))
    return delay

def local_gateway(args,kwargs):
    url=kwargs.get('url',args[2] if len(args)>2 else '')
    try:
        p=urlsplit(url)
        return p.scheme=='http' and p.hostname=='gateway' and p.port==8000 and p.path.rstrip('/')=='/v1' and not(p.username or p.password or p.query or p.fragment)
    except (ValueError,TypeError):
        return False

def with_embedding_retry(operation):
    @functools.wraps(operation)
    async def wrapped(*args,**kwargs):
        if not local_gateway(args,kwargs):
            return await operation(*args,**kwargs)
        deadline=time.monotonic()+RETRY_SECONDS
        for attempt in range(RETRY_ATTEMPTS):
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise TimeoutError('embedding_retry_budget_exceeded')
            try:
                async with asyncio.timeout(remaining):
                    return await operation(*args,**kwargs)
            except aiohttp.ClientResponseError as exc:
                if exc.status not in (429,503,504) or attempt+1>=RETRY_ATTEMPTS:
                    raise
                delay=retry_delay(exc.headers,attempt)
                if delay>300 or delay>=deadline-time.monotonic():
                    raise
                active=CURRENT_FILE.get()
                if active:
                    await publish_progress(active[0],'waiting',active[1],active[2],delay)
                log.warning('moara_embedding_retry status=%s attempt=%s delay_seconds=%s',exc.status,attempt+1,delay)
                await asyncio.sleep(delay)
                if active:
                    await publish_progress(active[0],'indexing',active[1],active[2])
    return wrapped
