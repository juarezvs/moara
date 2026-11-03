# Chat com rolagem da página

O chat permanece Angular 22 Standalone, com OnPush e o serviço de streaming existente. O projeto já utiliza Tailwind 4 e estilos próprios da identidade Moara; esta alteração usa os estilos existentes, sem acrescentar bibliotecas ou NgModule.

## Causa identificada

As respostas já eram artigos HTML, renderizados pelo componente MessageContent. O textarea existente serve para escrever a pergunta, não para exibir respostas.

O problema era a combinação de limites concorrentes: `.messages` nos estilos globais e em workbench.css usava `max-height:64vh` e `overflow-y:auto`; workbench-institutional.css aplicava `max-height:66vh`; chat-stream.scss acrescentava um limite calculado a partir da altura da tela e do compositor. O método scrollToResponse também alterava scrollTop desse painel.

## Estrutura implementada

As mensagens e seus wrappers têm altura natural, sem rolagem vertical própria. O documento é responsável pela rolagem. A coluna de leitura mantém a largura máxima existente, com perguntas e respostas alinhadas e largura adaptável ao celular.

O campo de envio permanece sticky no rodapé, com fundo opaco nos temas claro e escuro e espaço reservado pelo próprio fluxo do layout. Contexto e Opções foram movidos para composer-support, fora do rodapé sticky. Assim, a abertura dos painéis não aumenta o rodapé sobre a resposta.

O acompanhamento do streaming usa window.scrollTo, considerando a altura real do cabeçalho e do rodapé. A leitura manual pausa esse acompanhamento; o botão Acompanhar resposta permite retomá-lo. O indicador de processamento, o cursor, a atualização incremental e o destaque de código foram preservados.

O pipeline marked → DOMPurify → innerHTML permanece intacto em message-content.ts. Somente o textarea de entrada e o editor de rascunhos continuam sendo áreas de edição.

## Arquivos e revisão

- [Diff completo desta alteração](MOARA_PAGE_SCROLL_2026-11-02.diff)
- [Componente e rolagem](../moara/web/src/app/chat.ts)
- [Template e organização do rodapé](../moara/web/src/app/workbench.html)
- [Layout de leitura e responsividade](../moara/web/src/app/workbench-reading.css)
- [Estilos do streaming](../moara/web/src/app/chat-stream.scss)

Também foram removidos os limites anteriores em workbench.css, workbench-institutional.css e styles.css. Os estilos de painéis administrativos, navegação e tabelas não foram transformados em mensagens.

## Validação e operação

Publicação concluída em 02/11/2026. As 40 verificações do navegador passaram tanto em homologação quanto em produção; gateway e MCP estão saudáveis e os modelos principal e de embeddings permanecem residentes na GPU.

O build de produção Angular e os 10 testes existentes de SSE/streaming foram executados. Os testes no navegador utilizam uma resposta longa gerada pelo modelo real, com bloco de código e lista numerada, e verificam o comportamento em 1500×950, 390×844 e 320×640 pixels.

As verificações cobrem crescimento das mensagens além da altura da tela, ausência de scroll vertical nos ancestrais, rolagem da janela, rodapé sticky, leitura do final da resposta, ausência de overflow horizontal, streaming incremental, pausa/retomada, temas, destaque de código, painéis fora do rodapé e ausência de erros JavaScript.

Relatórios: [homologação](runtime/page-scroll-ui-stage.json), [produção](runtime/page-scroll-ui-public.json), [publicação](runtime/page-scroll-release.json) e [conferência final](runtime/page-scroll-final.json).

A imagem foi construída sobre a aplicação anterior, alterando somente /app/web. O overlay page-scroll-compose.yml troca apenas a imagem do gateway. O backend, o MCP, os dados e os modelos GPU são preservados. Para retorno à versão anterior, a cópia do script de composição está em backups/page-scroll-20261102/compose-before no servidor; a imagem anterior tem a tag moara-core:pre-page-scroll-app-20261102.
