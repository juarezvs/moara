from moara.identity.service import load_identity
from moara.identity.stream import IdentityPrefixGuard


def chunk(text=None, **delta):
    return {'choices': [{'index': 0, 'delta': {**({'content': text} if text is not None else {}), **delta}, 'finish_reason': None}]}


def content(chunks):
    return ''.join(c['delta'].get('content', '') for value in chunks for c in value.get('choices', []))


def test_fragmented_false_introduction_replaced():
    identity = load_identity()
    guard = IdentityPrefixGuard(identity)
    result = []
    for value in ['Eu ', 'sou ', 'Gem', 'ma. Como posso ajudar?']:
        result += guard.push(chunk(value))
    result += guard.flush()
    assert content(result) == identity.document.presentation
    assert guard.replaced


def test_normal_short_response_is_preserved():
    guard = IdentityPrefixGuard(load_identity())
    value = chunk('Aqui está a função solicitada.')
    assert guard.push(value) == []
    assert guard.flush() == [value]


def test_tool_arguments_are_unchanged():
    guard = IdentityPrefixGuard(load_identity())
    value = chunk(tool_calls=[{'index': 0, 'function': {'arguments': '{"name":"Gemma"}'}}])
    assert guard.push(value) == [value]
    assert not guard.replaced


def test_later_text_removed_after_false_introduction():
    guard = IdentityPrefixGuard(load_identity(), limit=12)
    output = guard.push(chunk('Eu sou Gemma.'))
    output += guard.push(chunk(' Uma ferramenta.', tool_calls=[{'index': 0, 'id': 't1'}]))
    assert content(output) == guard.identity.document.presentation
    assert output[-1]['choices'][0]['delta']['tool_calls'][0]['id'] == 't1'
