# Plano de implementação

Preparado em 26/10/2026. Execução incremental sobre a instalação real existente.

## Fase 1 — plano concreto de alterações para aprovação

1. Trazer uma cópia selecionada do código de `/home/nutec/ai-server` para este
   workspace, mantendo inicialmente caminhos/imports existentes. Excluir segredos,
   `.env`, dados corporativos, logs de consultas, backups, dependências e pesos.
   Registrar hashes de origem e revisar arquivos antes do primeiro commit de código.
2. Inspecionar código de backup e preservação, metadados de propriedade e horários
   de falha. Preparar correção em cópia isolada e cobrir negação de leitura,
   consistência e proteção do arquivo criptografado com dados fictícios. Não usar
   `chmod -R`, não divulgar segredos nem ignorar arquivos obrigatórios silenciosamente.
3. Registrar configuração/unidades/imagens atuais em preservação protegida no
   servidor. Executar o mecanismo existente de backup verificado após revisão;
   se a permissão impedir leitura, parar essa etapa e definir helper mínimo,
   sem ampliar o usuário da aplicação. Validar restauração em volumes descartáveis.
4. Publicar somente a correção de backup já testada, com cópia anterior preservada.
   A rotina deve falhar claramente se qualquer item obrigatório não puder ser lido;
   o timer só será considerado recuperado após uma execução e restauração verificadas.
5. Diagnosticar a unidade `ai-server` correlacionando journal, healthchecks e
   configuração Compose. Preparar correção de dependências/espera em homologação.
   Não executar o `deploy.sh` completo: ele baixa, reconstrói e modifica a stack.
6. Publicar apenas a alteração necessária à unidade/script de inicialização.
   Validar ciclo de vida em staging e estado do systemd. Reboot do host produtivo
   requer janela definida e backup validado; não está incluído nesta aprovação.
7. Conferir TLS/DNS/rotas existentes, redes e acesso externo. Não abrir portas nem
   alterar firewall nesta etapa. Se depender de sudo, usar terminal seguro do
   responsável; nunca enviar senha pelo chat ou gravá-la em arquivo.

**Escopo de aprovação:** cópia de código sem dados/segredos, homologação com dados
fictícios, preservação criptografada, restauração isolada e publicação das correções
restritas de backup/inicialização após aprovação dos testes. Preservar as rotas,
contas, histórico, modelos, bancos e volumes atuais. Sem migrações destrutivas,
reinicialização do host, alteração de credenciais ou novos acessos a bases reais.

**Aceite:** backup consistente restaurado em isolamento; erros de leitura
detectados; unidade de inicialização coerente com estado real; persistência e
recuperação testadas em staging; pendências de reboot/proteção externa explicitadas.

**Rollback:** restaurar exclusivamente o script/unidade alterado a partir da cópia
anterior, recarregar o systemd se necessário e confirmar containers/rotas. Não
restaurar bancos em produção automaticamente. Nunca executar `compose down -v`.

## Etapas seguintes e dependências

| Fase | Trabalho e condição de saída |
|---|---|
| 0 | Inventário, arquitetura, riscos e aprovação deste plano |
| 1 | Estabilização descrita acima; backup/restauração e persistência verificados |
| 2 | Licenças/digests; comparar Ollama e llama.cpp com checkpoint equivalente, 12/24/48 threads, NUMA e contexto 4K/8K; medir TTFT, tokens/s, RSS e fila; escolher padrão com evidências |
| 3 | Auditar backend existente; autenticação, RBAC/ACL, revogação, migrations e auditoria; endpoints protegidos e testes negativos |
| 4 | Auditar Angular existente; preencher lacunas de chat, anexos, histórico, streaming/cancelamento, acessibilidade e administração; build e E2E |
| 5 | Orquestrador e MOARA DEV com execução isolada, limites, rede bloqueada, plano/diff e aprovação; projeto fictício testado |
| 6 | RAG autorizado: extração/OCR, chunks, embeddings, busca híbrida e reranking; isolamento antes do LLM e citações verificáveis |
| 7 | SDK e conectores somente leitura; simuladores SECP/SARH/PJe; planos de consulta determinísticos, limites e testes de SSRF/ACL |
| 8 | Analytics reproduzível com definição, fonte, filtros e exportação em dados fictícios |
| 9 | Processos fictícios, linha do tempo, templates e minutas identificadas como rascunhos; revisão humana obrigatória |
| 10 | Grupos, prompts, templates e assistentes versionados; compartilhamento sem herdar acesso às fontes |
| 11 | AD/LDAPS e avaliação Kerberos; requer domínio, CA, grupos e conta autorizada fornecidos por canal seguro; testar revogação |
| 12 | MOARA FLOW com jobs duráveis, timeout, histórico, reexecução segura e aprovações; somente operações de teste iniciais |
| 13 | Homologação integrada, segurança, carga, concorrência, restore, documentação e aceite por evidências |

Antes de cada fase: ler status, conferir dependências, revisar código existente,
preparar testes e critério de rollback. Recursos encontrados devem ser reaproveitados
após validação; não refazer módulos aprovados apenas para mudar diretórios.
