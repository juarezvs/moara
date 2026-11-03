# Desenvolvimento de software de finalidade geral

A Moara Desenvolvedora passa a atender projetos pessoais, comerciais, educacionais, de entretenimento e institucionais. O vínculo com o tribunal deixou de ser critério para aceitar ou executar um fluxo de desenvolvimento.

A política de escopo 2.1.0 atua no classificador, no contexto central do modelo, no assistente selecionado, nas continuações de desenvolvimento e na geração/revisão de projetos. O modo de programação recebe instruções específicas para planejar, implementar, testar, corrigir e documentar, usando as ferramentas autorizadas do cliente. Quando não há ferramentas de execução, deve entregar código e instruções sem afirmar que executou algo.

A API moara-code mantém o protocolo Chat Completions, tool calls, resultados de ferramentas e streaming. O pacote de configuração do Continue usa o contexto do vínculo real de execução e um limite de saída compatível com o servidor, substituindo os antigos valores fixos 4096/1024. Os limites físicos de contexto e memória continuam tratados pela aplicação.

As instruções da Desenvolvedora foram publicadas pelo endpoint administrativo com controle de revisão, mantendo habilitação e ferramentas existentes. A revisão anterior está preservada, com acesso restrito, em backups/general-development-20261102/assistant-before.json. A identidade da plataforma, os cinco outros assistentes, suas permissões, a interface e o fundo permanecem preservados. Não foram concedidos novos privilégios, expostas credenciais ou habilitado acesso arbitrário ao servidor.

## Verificação

- 246 testes automatizados passaram.
- Geração real de site pessoal de receitas, sem exigência institucional.
- Geração de jogo da velha pela API para IDE, gravação do arquivo pela ferramenta do cliente e testes no navegador: jogadas, vitória, bloqueio após vitória, reinício e celular. O cliente valida os argumentos das ferramentas e pode devolver erros para correção.
- Continuação com resultado da ferramenta e resposta em streaming.
- Geração de projeto pessoal Python no módulo de projetos, aceitação da versão, aprovação vinculada ao digest e execução no sandbox existente. Os testes do aplicativo concluíram com saída DEMO_OK.
- Perguntas sobre a própria Moara e comparação jurídica com fontes oficiais continuaram funcionando.

Os relatórios general-development-*.json, em docs/runtime, identificam a imagem validada. O MCP, os modelos de linguagem e de embeddings e o timer de metadados foram conferidos. A inferência permaneceu residente.

## Operação

O overlay moara/infrastructure/general-development-compose.yml troca somente a imagem do gateway. A imagem anterior está preservada em moara-core:pre-general-development-app-20261102, com o wrapper anterior em backups/general-development-20261102/compose-before. Uma reversão integral deve restaurar também as instruções anteriores da Desenvolvedora por uma nova revisão administrativa, preservando o histórico.

Nenhuma migração de dados ou reinicialização do serviço de inferência foi necessária. Projetos reais continuam sujeitos às permissões efetivas do ambiente ou do IDE e ao mecanismo existente de execução isolada.
