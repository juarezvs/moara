# Plataforma institucional — implementação de 26/10/2026

## Autorização e escopo

O usuário autorizou expressamente todas as fases restantes e sua implementação sem
novas solicitações de autorização. A publicação depende dos testes técnicos, não
de uma nova aprovação administrativa no chat. Reboot do host, reinstalação e
alteração de credenciais não fazem parte desta entrega.

A implementação reutiliza Angular, FastAPI, PostgreSQL/pgvector, Redis, o gateway
de inferência e os conectores existentes. A árvore local continua excluindo
segredos, pesos e dados corporativos. Não há envio de dados institucionais a APIs
externas.

## Recursos implementados

- Biblioteca de documentos, prompts, templates, assistentes, projetos, processos,
  indicadores e workflows, com proprietário, grupo e versões.
- Conteúdo e resultados criptografados com a chave protegida existente. Títulos,
  metadados, vetores e índice lexical permanecem no PostgreSQL protegido por seus
  controles de acesso; não se afirma que esses índices sejam criptografados
  individualmente.
- Upload limitado a 4 MiB; texto UTF-8, CSV, PDF e DOCX. Extração em subprocesso
  com memória/CPU/tempo limitados. OCR Tesseract português/inglês para até 20
  páginas digitalizadas; PDF limitado a 100 páginas e 1.200 chunks.
- Embeddings locais de 768 dimensões, busca lexical em português e vetorial,
  combinação por reciprocal rank fusion e reranking com o modelo local autorizado.
  ACL aplicada antes da busca; fontes verificadas novamente antes da inferência
  e antes da leitura de resultados.
- Minutas identificadas como rascunho e referências com documento, página,
  ordinal, checksum e identificador. Referência válida não prova a correção
  jurídica de uma afirmação: revisão humana continua obrigatória.
- Templates determinísticos com campos declarados e exportação DOCX; análise
  de CSV por contagem, soma ou média, com filtros, definição e hash da fonte,
  além de exportação CSV protegida contra fórmulas.
- Propostas de código com arquivos, plano, diff e revisão por modelo local;
  aceitação versionada e execução separada mediante aprovação de digest/versão.
- Sandbox sem rede, sem credenciais ou Docker socket dentro da aplicação,
  entrada somente leitura, usuário não privilegiado, capabilities removidas,
  seccomp padrão, 256 MiB, uma CPU, 32 processos, 30 segundos e saída de 64 KiB.
  Worker do host usa somente protocolo fixo e imagens locais por ID imutável.
- Fluxos declarativos com busca autorizada, preenchimento de template, agregação
  e notificação **simulada**. Agendamentos mínimos de cinco minutos, fila
  persistente, idempotência, histórico, cancelamento e revalidação de identidade.
- Interface integrada em /moara/espaco, incluindo versões, uploads, execução,
  resultados, fontes, projetos e linha do tempo.

## Limites deliberados e dependências reais

A sandbox usa rootless Docker com seccomp; não equivale a uma VM ou gVisor.
GDS/microcode do host permanece pendente da infraestrutura. Execução deve ficar
restrita às contas explicitamente autorizadas; usuários comuns não recebem
development.execute por padrão.

A geração pode rejeitar JSON inválido ou citações inventadas em vez de aceitar
automaticamente a resposta. O reranker local usa uma chamada de LLM adicional;
não houve comparação conclusiva com um cross-encoder dedicado.

Não foram criadas integrações reais novas com PJe nem habilitadas escritas,
mensagens externas ou ações judiciais. Requerem endpoints, contratos e credenciais
institucionais específicos. Conectores existentes permanecem somente leitura e
seus testes usam dados fictícios. Kerberos/SPNEGO continua dependente de SPN,
keytab e configuração institucional; LDAPS existente foi testado com fixtures,
sem alegar autenticação com uma conta real do AD.

Modelos de grande porte não foram baixados indiscriminadamente. O catálogo e o
gerenciador existentes foram preservados. Os benchmarks medem um checkpoint
equivalente de 7B e não certificam qualidade jurídica nem capacidade institucional.

## Critérios de publicação

Build Angular, testes de contratos/criptografia/extração, PostgreSQL real, ACL,
revogação, execução aprovada, OCR, conectores, LDAPS, interface desktop/mobile,
inferência local sintética e backup/restore devem ter evidências recentes.

O estado efetivamente publicado, imagem, backup, migração e resultados finais são
registrados em DEPLOYMENT_STATUS.md e TEST_RESULTS.md. Este documento descreve a
implementação; não substitui os resultados de aceite.
