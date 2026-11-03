# Chat progressivo da Moara

## Estrutura implementada

O portal Angular mantém sua identidade visual e suas funcionalidades. O chat foi dividido em responsabilidades:

| Arquivo | Responsabilidade |
| --- | --- |
| moara/web/src/app/chat-stream.service.ts | POST autenticado, leitura incremental SSE/UTF-8, erros, estado e agrupamento de fragmentos |
| moara/web/src/app/chat.ts | Histórico, envio, cancelamento, composição da tarefa e rolagem após renderização |
| moara/web/src/app/workbench.html | Lista de mensagens, pensamento, botão de interrupção e retomada da rolagem |
| moara/web/src/app/chat-stream.scss | Indicador discreto com a marca M e controles de acompanhamento |
| moara/web/src/app/message-content.ts | Markdown sanitizado, fontes com hints, cursor e realce de código |
| moara/web/src/chat-code.css | Tema claro/escuro do código, cursor e movimento reduzido |
| moara/gateway/chat_delivery.py | Entrega progressiva de respostas já verificadas pela aplicação |

## Estado e fluxo

Os estados do ChatStreamService são idle, thinking, streaming e completed. O envio começa em thinking, incluindo o período de preparação e conferência. O primeiro fragmento de texto muda o estado para streaming. A confirmação SSE [DONE] conclui a resposta. Erro ou cancelamento retorna a idle e preserva os caracteres recebidos; o chat marca a resposta parcial como interrompida.

O serviço recebe callbacks onText e onEvent. Não conhece elementos HTML nem grava histórico. O ChatPage usa os eventos reais da aplicação para exibir as etapas de processamento. O indicador não exibe raciocínio privado do modelo.

O primeiro fragmento é mostrado imediatamente. Os seguintes são agrupados em janelas de 32 ms; a última janela é descarregada também em caso de interrupção. Não há um temporizador que redigite cada caractere no cliente.

O backend já retinha as respostas do portal para verificar referências jurídicas e documentais. Essa proteção foi preservada: texto sujeito à conferência começa a ser entregue somente depois de aprovado, em pequenos eventos SSE, com intervalos de 16 ms. Isso é entrega progressiva de texto aprovado, não transmissão dos tokens brutos do modelo durante a conferência. O transporte direto já usado pelos clientes de desenvolvimento continua disponível conforme sua política existente.

## Renderização e rolagem

ChatPage e MessageContent usam explicitamente ChangeDetectionStrategy.OnPush e signals. O renderizador existente marked foi mantido, com DOMPurify; não foi necessário adicionar outra biblioteca. highlight.js, já presente no projeto, realça linguagens registradas sem autodetecção.

Há um cache limitado a 64 blocos de código e 200 mil caracteres de chaves. Blocos em formação no fim da resposta ficam como texto de código até estabilizarem, evitando realce repetido. Código acima de 50 mil caracteres e linguagens desconhecidas permanecem em texto, preservando legibilidade e evitando trabalho excessivo.

A rolagem acompanha o fim da resposta após o Angular atualizar o DOM, incluindo a área interna quando ela tem rolagem. Roda do mouse, toque, teclas de leitura ou interação na conversa pausam o acompanhamento. O botão Acompanhar resposta retoma essa ação. O fim da geração mantém a posição final; esta entrega substitui a regra anterior que reposicionava a tela no início da resposta.

O cursor só aparece na última resposta enquanto streaming está ativo. O CSS respeita movimento reduzido, tema escuro e alto contraste.

## Testes e implantação

Os testes de transporte cobrem fragmentação UTF-8/SSE, agrupamento de rajadas, preservação da resposta parcial, erro, falta da confirmação final e concorrência. Os testes do backend conferem integridade Unicode, metadados, término, cancelamento e preservação do contrato de ferramentas.

O teste de navegador usa TLS e tráfego SSE real, sem interceptar e armazenar a resposta inteira antes de mostrá-la. O candidato é acessado por um proxy TLS privado, sem publicar portas. Os relatórios registram leituras da rede, atualizações visuais e tarefas longas da thread principal. Conversas sintéticas são arquivadas e a sessão de teste é revogada.

Referências primárias utilizadas:

- [Angular: ChangeDetectionStrategy](https://angular.dev/api/core/ChangeDetectionStrategy)
- [Angular: signals e renderização](https://angular.dev/guide/zoneless)
- [highlight.js: API de realce](https://highlightjs.readthedocs.io/en/latest/api.html)
