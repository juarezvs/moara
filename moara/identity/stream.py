"""Guard only a bounded visible introduction; never modify native tool calls."""
from copy import deepcopy


class IdentityPrefixGuard:
    def __init__(self, identity, limit=128):
        self.identity = identity
        self.limit = limit
        self.pending = []
        self.text = ''
        self.decided = False
        self.replaced = False

    def push(self, chunk):
        if self.decided:
            if not self.replaced:
                return [chunk]
            value = deepcopy(chunk)
            for choice in value.get('choices', []):
                choice.get('delta', {}).pop('content', None)
            return [value]
        self.pending.append(chunk)
        for choice in chunk.get('choices', []):
            self.text += choice.get('delta', {}).get('content') or ''
        finished = any(c.get('finish_reason') for c in chunk.get('choices', []))
        tool = any(c.get('delta', {}).get('tool_calls') for c in chunk.get('choices', []))
        if len(self.text) >= self.limit or finished or tool:
            return self.flush()
        return []

    def flush(self):
        if self.decided:
            return []
        self.decided = True
        self.replaced = self.identity.rejects_self_identification(self.text)
        output = self.pending
        self.pending = []
        if not self.replaced:
            return output
        output = deepcopy(output)
        inserted = False
        for chunk in output:
            for choice in chunk.get('choices', []):
                delta = choice.get('delta', {})
                if 'content' in delta:
                    delta['content'] = self.identity.document.presentation if not inserted else ''
                    inserted = True
        return output
