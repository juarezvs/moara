# Decisões de segurança

26/10/2026.

- SSH usa a credencial existente, sem solicitar senha, e verificação estrita de
  known_hosts. Não armazenar credenciais no código, chat, scripts ou logs.
- Inventário não lê segredos, conteúdo de bancos, documentos, prompts ou respostas
  de conectores. Metadados técnicos locais ficam fora de Git por padrão.
- Nenhuma conta/credencial é redefinida. Autorização de acesso ao servidor não
  substitui aprovação de acesso aos dados corporativos.
- Corrigir backup mantendo menor privilégio: não tornar segredos legíveis para
  todos, ignorar arquivos obrigatórios ou montar Docker socket na aplicação.
- Staging e testes usam dados fictícios; acesso a bases institucionais fica sujeito
  à autorização específica prevista na especificação.
- Documentos e saídas de ferramentas são dados não confiáveis. Políticas e ACLs
  são verificadas pelo backend, sem delegar autorizações ao LLM.
- Não foi autorizada formatação, exclusão de volumes ou migração destrutiva.
- O documento fornecido exige aprovação do plano entre Fases 0 e 1. O plano
  preparado limita explicitamente as primeiras alterações e seu rollback.
