# Entrada principal da Moara

Publicado em 30/10/2026. O endereço https://moara.am.trf1.gov.br/ encaminha para https://moara.am.trf1.gov.br/moara/chat, reunindo a entrada principal e o ambiente de trabalho já existente. A marca, as cores, os recursos de acessibilidade e a autenticação da Moara foram preservados.

Sem sessão, o usuário encontra a página de autenticação institucional. Após autenticar, retorna ao destino solicitado; o destino padrão é o chat. Uma sessão existente do chat anterior pode ser reconhecida pelo mecanismo de autenticação já disponível, sem alteração de senha.

O chat anterior permanece acessível por https://moara.am.trf1.gov.br/chat-anterior, que encaminha para `/?interface=anterior`. Os links de histórico e autenticação alternativa usam essa exceção para evitar ciclos. Históricos antigos, APIs, arquivos, WebSockets e rotas de conversas existentes continuam disponíveis.

## Implantação e validação

- Imagem ativa: `moara-core:primary-entry-20261030`, baseada na imagem de produção imediatamente anterior. Somente os arquivos compilados do frontend foram adicionados; as correções de análise documental e orçamento de contexto foram preservadas.
- Overlay final: `moara/infrastructure/site-entry-compose.yml`.
- Caddy: somente GET e HEAD no caminho exato `/` são encaminhados por 302, com `Cache-Control: no-store`; `interface=anterior` é a exceção explícita.
- Não houve migração de banco nem reinicialização do servidor de inferência.
- Backup cifrado: `moara-before-migration-20261030T223200Z.tar.enc`. Restauração isolada verificada em 30/10/2026 às 18:33:28, horário de Manaus, incluindo PostgreSQL, arquivos, SQLite, configurações e certificados.
- Testes em Chromium isolado: entrada anônima e autenticada, marca, autenticação alternativa sem ciclo, seis abas, resposta sobre habilidades, tela pequena, chat anterior, arquivos visuais e endereço canônico. Conteúdo sintético arquivado e sessões nativas de teste revogadas.
- Solicitação real de reescrita executada pela GPU em 3,72 segundos no teste público; esse tempo é uma medição pontual, não uma garantia para outras tarefas. Nenhum erro JavaScript foi observado no percurso validado.
- Evidências: `docs/runtime/primary-entry-stage.json`, `primary-entry-ui.json`, `primary-entry-http.json`, `primary-entry-login.png` e `primary-entry-workbench.png`.
- O teste privado confere o redirecionamento por HTTP e abre o chat candidato explicitamente: a interceptação de Playwright não se repete para todos os destinos de uma cadeia de redirecionamentos. O teste público percorre efetivamente a raiz e o redirecionamento real.

## Recuperação

Os arquivos anteriores estão em `backups/primary-entry-20261030/`: `Caddyfile-before` e `compose-before`. A imagem anterior foi preservada como `moara-core:pre-primary-entry-20261030`.

Para reverter, restaurar o conteúdo do Caddyfile anterior **no mesmo arquivo**, mantendo o inode do bind mount, e restaurar o wrapper `moara/infrastructure/scripts/compose.sh`, mantendo o modo 755. Executar o wrapper com `up -d --no-deps moara-gateway`; reiniciar somente `ai-server-caddy-1`. O Caddy está com a API administrativa desativada, portanto `caddy reload` não é o procedimento operacional disponível. Conferir `/moara/api/v1/ready`, a raiz, o chat canônico e o acesso ao chat anterior. Não remover volumes nem executar `compose down`.

As integrações oficiais pendentes de PJe/SEI e os limites de confirmação de vigência e jurisprudência permanecem como documentados nas respectivas entregas.
