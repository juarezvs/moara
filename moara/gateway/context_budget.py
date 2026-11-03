"""Bounded context planning; never truncate the current question or sources."""
import json,math
from fastapi import HTTPException

def input_size(messages,tools):
    return len(json.dumps({'messages':messages,'tools':tools},ensure_ascii=False).encode())

def fit(messages,tools,context_length,requested_output,allow_history_window=False):
    original=input_size(messages,tools);minimum=min(requested_output,512)
    users=[i for i,m in enumerate(messages) if m.get('role')=='user']
    systems=[m for m in messages if m.get('role')=='system']
    options=[(messages,0,0)]
    if allow_history_window:
        for turns,start in enumerate(users[1:],1):
            kept=systems+[m for m in messages[start:] if m.get('role')!='system']
            options.append((kept,sum(m.get('role')!='system' for m in messages[:start]),turns))
    for candidate,omitted,turns in options:
        context_instruction=''
        if omitted:
            context_instruction='\nCONTEXTO DESTA RESPOSTA: turnos anteriores não foram incluídos por limite de espaço. Use apenas a pergunta atual e as fontes presentes; não presuma detalhes dos turnos ausentes.'
            candidate=[dict(m) for m in candidate]
            candidate[0]['content']+=context_instruction
        size=input_size(candidate,tools)
        available=context_length-math.ceil(size/3)
        if available<minimum:continue
        output=min(requested_output,available)
        info={'context_length':context_length,'original_input_bytes':original,'input_bytes':size,
              'estimation':'utf8_bytes_div_3','requested_output_tokens':requested_output,'output_tokens_limit':output,
              'omitted_messages':omitted,'omitted_turns':turns,'current_input_truncated':False}
        notice=''
        if omitted:notice=f'**Contexto desta resposta:** mantive a pergunta mais recente e as fontes enviadas nesta solicitação. {omitted} mensagens anteriores ficaram fora do contexto do modelo; elas continuam no histórico.\n\n'
        elif output<requested_output:notice='**Contexto desta resposta:** ajustei a extensão máxima da redação ao espaço disponível, preservando os textos enviados.\n\n'
        return candidate,output,info,notice
    raise HTTPException(413,'O conteúdo atual ainda excede a capacidade do modelo. Inicie uma nova análise com os documentos selecionados ou divida os arquivos em partes; nenhum texto foi cortado.',
        headers={'X-Moara-Error-Code':'estimated_context_budget_exceeded'})

def prefix_notice(result,notice):
    if notice:
        for choice in result.get('choices',[]):
            message=choice.get('message',{})
            if isinstance(message.get('content'),str):message['content']=notice+message['content']
    return result
