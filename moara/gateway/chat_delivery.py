"""Progressive delivery of already approved text; never bypass output verification."""
import asyncio,json

def event(value):
    return 'data: '+json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n\n'

async def approved_stream(result):
    envelope={k:result[k] for k in ('id','created','model') if k in result}
    envelope['object']='chat.completion.chunk'
    if 'moara' in result:
        yield event({**envelope,'moara':result['moara'],'choices':[]})
    for position,choice in enumerate(result.get('choices',[])):
        index=choice.get('index',position);message=choice.get('message',{})
        opening={k:message[k] for k in ('role','tool_calls') if message.get(k) is not None}
        if opening:yield event({**envelope,'choices':[{'index':index,'delta':opening,'finish_reason':None}]})
        text=message.get('content') or ''
        # Unicode characters remain intact. Pace only approved output, not model reasoning.
        width=max(24,min(128,len(text)//96))
        for offset in range(0,len(text),width):
            yield event({**envelope,'choices':[{'index':index,'delta':{'content':text[offset:offset+width]},'finish_reason':None}]})
            await asyncio.sleep(.016)
        yield event({**envelope,'choices':[{'index':index,'delta':{},'finish_reason':choice.get('finish_reason') or 'stop'}]})
    yield 'data: [DONE]\n\n'
