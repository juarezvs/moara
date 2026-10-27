/* Additive native-chat feedback. No credentials or document contents are persisted. */
(() => {
  'use strict';
  if (window.__moaraFeedback) return;
  window.__moaraFeedback = true;
  const nativeFetch = window.fetch.bind(window);
  let panel, generation, generationRow;
  const cards = new Set();
  const contextError = 'O histórico e os trechos do arquivo ultrapassaram o limite desta conversa. Abra uma nova conversa, anexe o arquivo e faça uma pergunta específica.';
  function mount() {
    const target = document.querySelector('#message-input-container');
    if (!target) return;
    if (!panel) { panel = document.createElement('section'); panel.id = 'moara-feedback'; panel.setAttribute('aria-label', 'Atividade da Moara'); }
    if (!panel.isConnected) target.prepend(panel);
  }
  function card(name) {
    mount();
    const row = document.createElement('div'); row.className = 'moara-feedback-card';
    const title = document.createElement('strong'); title.textContent = name;
    const label = document.createElement('span'); label.setAttribute('role', 'status');
    const bar = document.createElement('progress'); bar.max = 100; bar.setAttribute('aria-label', name);
    const close = document.createElement('button'); close.type = 'button'; close.textContent = 'Fechar'; close.hidden = true;
    row.append(title, label, bar, close);
    const item = {row, label, bar, close, closed:false, update(text, percent=null) {
      if (label.textContent !== text) label.textContent = text;
      if (percent === null) bar.removeAttribute('value'); else bar.value = Math.max(0, Math.min(100, percent));
    }, finish(text, success=false) {
      this.update(text, success ? 100 : null); bar.hidden = !success; close.hidden = false;
    }};
    close.onclick = () => { item.closed = true; row.remove(); cards.delete(item); };
    cards.add(item); if (panel) panel.append(row);
    return item;
  }
  function status(text) {
    if (!generationRow || !generationRow.row.isConnected) generationRow = card('Resposta da Moara');
    generationRow.update(text); generationRow.bar.hidden = true;
  }
  function end(text) {
    generation = false;
    if (generationRow) { if (text) generationRow.finish(text); else { generationRow.row.remove(); cards.delete(generationRow); generationRow = null; } }
  }
  async function poll(item, id, headers) {
    const deadline = Date.now() + 3600000;
    while (!item.closed && Date.now() < deadline && !location.pathname.startsWith('/auth')) {
      try {
        const response = await nativeFetch('/api/v1/files/' + encodeURIComponent(id) + '/process/status', {headers});
        if (response.status === 401 || response.status === 403) { item.finish('Sessão encerrada ou acesso indisponível.'); return; }
        if (response.ok) {
          const data = await response.json(), p = data.progress || {};
          if (data.status === 'completed') { item.finish('Pronto para consulta — 100%', true); return; }
          if (data.status === 'failed') { item.finish('Não foi possível processar este arquivo. Tente enviá-lo novamente.'); return; }
          if (p.stage === 'indexing') item.update('Indexando: ' + p.percent + '% (' + p.completed_chunks + '/' + p.total_chunks + ' trechos)', p.percent);
          else if (p.stage === 'waiting') item.update('Aguardando capacidade para continuar a indexação…', p.percent);
          else if (p.stage === 'saving') item.update('Indexação: 100%. Salvando para consulta…', 100);
          else item.update('Extraindo o texto do arquivo…');
        }
      } catch (_) { item.update('Reconectando para acompanhar o processamento…'); }
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    if (!item.closed) item.finish('Acompanhamento encerrado. Confira o estado do anexo no chat.');
  }
  function upload(url, init, file) {
    const item = card(file.name); item.update('Enviando: 0%', 0);
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const headers = new Headers(init.headers);
      xhr.open('POST', url.href);
      xhr.withCredentials = init.credentials === 'include';
      headers.forEach((value, key) => xhr.setRequestHeader(key, value));
      const abort = () => xhr.abort();
      const cleanup = () => init.signal?.removeEventListener('abort', abort);
      xhr.upload.onprogress = event => {
        if (event.lengthComputable) { const n = Math.floor(100 * event.loaded / event.total); item.update('Enviando: ' + n + '%', n); }
      };
      xhr.upload.onload = () => item.update('Envio concluído. Extraindo o texto…');
      xhr.onerror = () => { cleanup(); item.finish('Falha de conexão ao enviar o arquivo.'); reject(new TypeError('Failed to fetch')); };
      xhr.onabort = () => { cleanup(); item.finish('Envio cancelado.'); reject(new DOMException('Aborted', 'AbortError')); };
      xhr.onload = () => {
        cleanup();
        const responseHeaders = new Headers();
        xhr.getAllResponseHeaders().trim().split(/[\r\n]+/).forEach(line => { const at = line.indexOf(':'); if (at > 0) responseHeaders.append(line.slice(0, at), line.slice(at+1).trim()); });
        const response = new Response(xhr.responseText, {status:xhr.status, statusText:xhr.statusText, headers:responseHeaders});
        if (response.ok) {
          try { const data = JSON.parse(xhr.responseText); if (data.id && url.searchParams.get('process') !== 'false') void poll(item, data.id, headers); else item.finish('Envio concluído — 100%', true); }
          catch (_) { item.finish('Envio concluído. Confira o anexo no chat.'); }
        } else item.finish('O servidor não aceitou o arquivo. Confira a mensagem do chat.');
        resolve(response);
      };
      if (init.signal?.aborted) { cleanup(); item.finish('Envio cancelado.'); reject(new DOMException('Aborted', 'AbortError')); return; }
      init.signal?.addEventListener('abort', abort, {once:true});
      xhr.send(init.body);
    });
  }
  window.fetch = async function(input, init = {}) {
    const url = new URL(input instanceof Request ? input.url : input, location.href);
    const method = (init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    if (url.origin !== location.origin) return nativeFetch(input, init);
    if (method === 'POST' && /^\/api\/v1\/files\/?$/.test(url.pathname) && init.body instanceof FormData) {
      const file = init.body.get('file');
      if (file instanceof File) return upload(url, init, file);
    }
    const chat = method === 'POST' && url.pathname === '/api/chat/completions';
    if (chat) { generation = true; status('Moara está preparando a resposta…'); }
    try {
      const response = await nativeFetch(input, init);
      if (chat && !response.ok) {
        const error = await response.clone().text();
        end(error.includes('estimated_context_budget_exceeded') ? contextError : 'Não foi possível concluir a resposta. Confira a mensagem do chat.');
      }
      return response;
    } catch (error) { if (chat) end('A conexão foi interrompida. Tente novamente.'); throw error; }
  };
  // Observe the existing same-origin Socket.IO channel without changing its messages.
  const NativeSocket = window.WebSocket;
  window.WebSocket = class extends NativeSocket {
    constructor(url, protocols) {
      super(url, ...(protocols === undefined ? [] : [protocols]));
      const address = new URL(url, location.href);
      if (address.host !== location.host || !address.pathname.startsWith('/ws/')) return;
      this.addEventListener('message', event => {
        if (typeof event.data !== 'string' || !event.data.startsWith('42')) return;
        try {
          const at = event.data.indexOf('['), packet = JSON.parse(event.data.slice(at));
          const message = packet[1];
          if (!message?.message_id || !document.getElementById('message-' + message.message_id)) return;
          const type = message.data?.type, data = message.data?.data;
          if (type === 'chat:message:error') { end(JSON.stringify(data).includes('estimated_context_budget_exceeded') ? contextError : 'Não foi possível concluir a resposta. Confira a mensagem do chat.'); return; }
          if (type === 'chat:tasks:cancel' || data?.done === true) { end(); return; }
          if (!generation) return;
          if (['chat:completion','response:completion','chat:message:delta','message'].includes(type) && (data?.content || data?.choices?.[0]?.delta?.content)) status('Moara está escrevendo a resposta…');
        } catch (_) { /* Native handling remains authoritative. */ }
      });
    }
  };
  document.addEventListener('click', event => {
    if (event.target.closest?.('#message-input-container button[aria-label="Stop"], #message-input-container button[aria-label="Parar"]')) end('Resposta interrompida.');
  }, true);
  setInterval(() => {
    if (location.pathname.startsWith('/auth')) {
      cards.forEach(item => { item.closed = true; item.row.remove(); }); cards.clear(); generation = false; generationRow = null; return;
    }
    mount(); if (panel) cards.forEach(item => { if (!item.row.isConnected) panel.append(item.row); });
  }, 1000);
})();
