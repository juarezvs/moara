"""CPU-aware preference tiers; authorization and capabilities remain in route()."""
import unicodedata


def preferences(messages):
    last = next((m.get('content', '') for m in reversed(messages) if m.get('role') == 'user'), '')
    text = unicodedata.normalize('NFKD', last if isinstance(last, str) else '').encode('ascii', 'ignore').decode().casefold()
    software = any(word in text for word in (
        'codigo', 'python', 'typescript', 'javascript', 'sql', 'programa', 'software',
        'bug', 'teste', 'api ', 'funcao', 'docker', 'refator', 'repositorio', 'code', 'debug'))
    if software:
        if any(word in text for word in ('compatibilidade legada', 'sistema legado', 'legacy', 'migracao de software')):
            return 'coding', 'task_software_legacy', ['llama31-70b', 'llama33-70b', 'coding', 'qwen25-coder-32b']
        if any(word in text for word in ('arquitetura', 'auditoria de seguranca', 'revisao profunda', 'security audit')):
            return 'coding', 'task_software_deep', ['llama33-70b', 'llama31-70b', 'coding', 'qwen25-coder-32b']
        if len(text) > 280 or any(word in text for word in ('refator', 'varios arquivos', 'multiplos arquivos', 'testes', 'repositorio', 'depur')):
            return 'coding', 'task_software_complex', ['qwen25-coder-32b', 'coding', 'deepseek-coder-v2-lite', 'qwen25-coder-7b']
        return 'coding', 'task_software', ['general', 'qwen25-coder-7b', 'coding', 'qwen25-coder-32b']
    category = 'fast' if len(text) < 180 and len(messages) < 4 else 'general'
    return category, 'task_short' if category == 'fast' else 'task_general', ['general', 'gemma4-12b', 'fast'] if category == 'fast' else ['general', 'gemma4-12b', 'llama33-70b', 'llama31-70b']


def automatic_order(profiles, messages):
    category, reason, preferred = preferences(messages)
    rank = {identifier: index for index, identifier in enumerate(preferred)}
    eligible = [p for p in profiles if p['settings'].get('auto_eligible', p['id'] in {'coding', 'general', 'fast'})]
    return sorted(eligible, key=lambda p: (0 if p['id'] in rank else 1, rank.get(p['id'], 99), p['category'] != category, p['id'])), reason
