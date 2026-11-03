'use strict';

// Request-only compaction. The saved Continue conversation and project files
// are never changed. No summarization model, network request, or tool execution.
const bytes = value => Buffer.byteLength(JSON.stringify(value), 'utf8');
const text = message => typeof message.content === 'string' ? message.content
  : Array.isArray(message.content) ? message.content.filter(p => p.type === 'text').map(p => p.text).join('\n') : '';
const callId = message => message.tool_call_id || message.toolCallId;
const calls = message => message.toolCalls || message.tool_calls || [];

function excerpt(value, limit, label) {
  if (value.length <= limit) return value;
  const tail = Math.min(220, Math.floor(limit / 4));
  return value.slice(0, limit - tail) + '\n[' + label + ': middle omitted from MODEL CONTEXT only; full result remains in the saved history. Read a small relevant range from disk if needed.]\n' + value.slice(-tail);
}

function shrink(message, limit = 1400) {
  const copy = { ...message };
  if (message.role === 'tool') copy.content = excerpt(text(message), limit, 'TOOL OUTPUT EXCERPT');
  if (message.role === 'assistant') {
    copy.content = excerpt(text(message), 500, 'EARLIER ASSISTANT TEXT');
    if (calls(message).length) copy[message.toolCalls ? 'toolCalls' : 'tool_calls'] = calls(message).map(call => {
      const fn = { ...call.function };
      try {
        const args = JSON.parse(fn.arguments || '{}');
        for (const key of Object.keys(args)) {
          if (typeof args[key] === 'string' && args[key].length > 800 && !/path|filename|uri/i.test(key)) {
            args[key] = '[Earlier executed tool argument omitted from model context. Original arguments remain in saved history; inspect the file/result before editing.]';
          }
        }
        fn.arguments = JSON.stringify(args);
      } catch { /* Keep original malformed arguments so their failure is visible. */ }
      return { ...call, function: fn };
    });
  }
  return copy;
}

function compactMessages(messages, tools = [], options = {}) {
  const maxBytes = options.maxBytes || 14000;
  const beforeBytes = bytes({ messages, tools });
  if (beforeBytes <= maxBytes) return { messages, compacted: false, beforeBytes, afterBytes: beforeBytes };

  const systems = messages.filter(m => m.role === 'system');
  const users = messages.map((m, index) => m.role === 'user' ? index : -1).filter(i => i >= 0);
  if (!users.length) return { messages, compacted: false, beforeBytes, afterBytes: beforeBytes };
  const latestUserIndex = users.at(-1);
  const anchors = users.length > 1 ? [messages[users[0]], messages[latestUserIndex]] : [messages[latestUserIndex]];
  // Preserve current user instructions verbatim. An oversized individual user
  // message must still be handled explicitly, rather than silently cut.
  const groups = [];
  for (let index = latestUserIndex + 1; index < messages.length; index++) {
    const message = messages[index];
    if (message.role === 'assistant' && calls(message).length) {
      const group = [message];
      const ids = new Set(calls(message).map(c => c.id));
      while (index + 1 < messages.length && messages[index + 1].role === 'tool') {
        const result = messages[++index];
        if (ids.has(callId(result))) group.push(result);
      }
      // Do not include partially executed calls in a compacted request.
      if (calls(message).every(c => group.slice(1).some(m => callId(m) === c.id))) groups.push(group);
    } else if (message.role !== 'tool' && message.role !== 'system' && message.role !== 'user' && text(message)) {
      groups.push([message]);
    }
  }

  const receipts = [];
  for (let index = 0; index < messages.length; index++) {
    for (const call of calls(messages[index])) {
      let path = '';
      try {
        const args = JSON.parse(call.function.arguments || '{}');
        path = String(args.filepath || args.file_path || args.dirPath || '').slice(0, 180);
      } catch { /* No guessed path. */ }
      let result;
      for (let next = index + 1; next < messages.length && messages[next].role === 'tool'; next++) {
        if (callId(messages[next]) === call.id) result = messages[next];
      }
      if (result) receipts.push(call.function.name + (path ? ' ' + path : '') + ' [result recorded]');
    }
  }
  const planRecentlyRead = groups.slice(-3).some(group => group.some(message => calls(message).some(call => {
    if (call.function.name !== 'read_file') return false;
    try { return /(?:^|[\\/])\.moara[\\/]plano\.md$/.test(JSON.parse(call.function.arguments || '{}').filepath || ''); }
    catch { return false; }
  })));
  const recovery = planRecentlyRead
    ? 'The plan was read in the retained recent tool results. Use it and advance implementation; do not reread unchanged files.'
    : 'Read .moara/plano.md once to recover the task state, then advance the next incomplete deliverable.';
  const checkpoint = {
    role: 'assistant',
    content: '[AUTOMATIC CONTEXT CHECKPOINT]\nEarlier conversation was compacted to fit the model. The full saved history and disk files are unchanged. Tool receipts below prove only that a result was returned, not that every operation succeeded. Do not repeat completed actions blindly. ' + recovery + ' Verify actual files/tests before claiming completion.\nRecent recorded operations:\n' + receipts.slice(-18).join('\n')
  };
  let recent = groups.slice(-3).map(group => group.map(message => shrink(message)));
  let result = [...systems, ...anchors, checkpoint, ...recent.flat()];
  while (recent.length > 1 && bytes({ messages: result, tools }) > maxBytes) {
    recent.shift();
    result = [...systems, ...anchors, checkpoint, ...recent.flat()];
  }
  if (bytes({ messages: result, tools }) > maxBytes) {
    checkpoint.content = checkpoint.content.split('Recent recorded operations:')[0] + 'Recent operations:\n' + receipts.slice(-5).join('\n');
    recent = recent.map(group => group.map(message => shrink(message, 500)));
    result = [...systems, ...anchors, checkpoint, ...recent.flat()];
  }
  const afterBytes = bytes({ messages: result, tools });
  return { messages: result, compacted: true, beforeBytes, afterBytes, overBudget: afterBytes > maxBytes };
}

module.exports = { compactMessages };
