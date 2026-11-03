'use strict';
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { compactMessages } = require('./moara-context.cjs');

function history(count = 260) {
  const result = [{ role: 'system', content: 'Use real tools.' }, { role: 'user', content: 'Build FastAPI + Angular + PostgreSQL, CRUD with photo upload, in Docker.' }];
  for (let i = 0; i < count; i++) {
    result.push({ role: 'assistant', content: '', tool_calls: [{ id: 'call_' + i, type: 'function', function: { name: 'create_new_file', arguments: JSON.stringify({ filepath: 'src/file' + i + '.py', contents: 'x'.repeat(4000) }) } }] });
    result.push({ role: 'tool', tool_call_id: 'call_' + i, content: 'File created successfully.' });
  }
  return result;
}

test('long chains fit a bounded packet, preserve the user task and leave saved history untouched', () => {
  const input = history(); const original = JSON.stringify(input);
  const result = compactMessages(input);
  assert.equal(result.compacted, true); assert.ok(result.afterBytes < 14000);
  assert.deepEqual(result.messages.find(m => m.role === 'user'), input[1]);
  assert.equal(JSON.stringify(input), original);
  assert.ok(result.messages.some(m => String(m.content).includes('AUTOMATIC CONTEXT CHECKPOINT')));
});

test('every retained native tool result has its matching valid call', () => {
  const result = compactMessages(history());
  for (let i = 0; i < result.messages.length; i++) {
    const message = result.messages[i];
    if (message.role !== 'tool') continue;
    let j = i - 1; while (result.messages[j]?.role === 'tool') j--;
    assert.ok(result.messages[j]?.tool_calls.some(c => c.id === message.tool_call_id));
    for (const call of result.messages[j].tool_calls) assert.doesNotThrow(() => JSON.parse(call.function.arguments));
  }
});

test('large file reads are explicitly marked excerpts and keep disk contents unchanged', () => {
  const input = history(1); input[3].content = 'BEGIN\n' + 'line of source\n'.repeat(3000) + 'END';
  const result = compactMessages(input);
  assert.match(result.messages.at(-1).content, /TOOL OUTPUT EXCERPT/);
  assert.match(result.messages.at(-1).content, /END$/);
  assert.ok(input[3].content.length > 30000); assert.ok(result.afterBytes < 14000);
});

test('short conversations pass through without any change', () => {
  const input = history(1); const result = compactMessages(input);
  assert.equal(result.compacted, false); assert.equal(result.messages, input);
});

test('latest user steering remains verbatim across a long older task', () => {
  const input = history(); const steering = { role: 'user', content: 'Keep PostgreSQL and add employee search.' };
  input.push(steering); const result = compactMessages(input);
  assert.deepEqual(result.messages.filter(m => m.role === 'user'), [input[1], steering]);
});

test('a single oversized user request is never silently shortened', () => {
  const input = [{ role: 'user', content: 'User requirements '.repeat(3000) }];
  const result = compactMessages(input);
  assert.equal(result.messages.find(m => m.role === 'user').content, input[0].content);
  assert.equal(result.overBudget, true);
});

test('unmatched tool results cannot be sent as orphan messages', () => {
  const input = history(); input.push({ role: 'tool', tool_call_id: 'missing', content: 'bad'.repeat(10000) });
  const result = compactMessages(input);
  assert.ok(!result.messages.some(m => m.tool_call_id === 'missing'));
});

test('Continue internal camelCase call fields retain the same protocol guarantees', () => {
  const input = history().map(message => {
    const copy = { ...message };
    if (copy.tool_calls) { copy.toolCalls = copy.tool_calls; delete copy.tool_calls; }
    if (copy.tool_call_id) { copy.toolCallId = copy.tool_call_id; delete copy.tool_call_id; }
    return copy;
  });
  const result = compactMessages(input);
  assert.ok(result.messages.at(-2).toolCalls?.length);
  assert.equal(result.messages.at(-1).toolCallId, result.messages.at(-2).toolCalls[0].id);
  assert.doesNotThrow(() => JSON.parse(result.messages.at(-2).toolCalls[0].function.arguments));
  assert.ok(result.afterBytes < 14000);
});

test('a recently read plan does not trigger a new plan-reading loop', () => {
  const input = history();
  input.at(-2).tool_calls[0].function = { name: 'read_file', arguments: JSON.stringify({ filepath: '.moara/plano.md' }) };
  input.at(-1).content = 'Implement the frontend next.';
  const result = compactMessages(input);
  assert.ok(result.messages.some(m => String(m.content).includes('The plan was read in the retained recent tool results')));
});
