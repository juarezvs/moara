# Navegação lateral e etapas de processamento

A navegação do ambiente de trabalho foi reorganizada em uma coluna à direita: Início, Histórico, Documentos, Modelos, Referências e Acervo. A organização vale também para telas pequenas. A orientação acessível das abas é vertical, com navegação por setas para cima/baixo, Home e End, mantendo a seleção e as permissões existentes.

Durante uma solicitação, a marca M da Moara recebe uma animação discreta de opacidade e escala. O texto informa a operação real da aplicação:

- preparação e envio da solicitação;
- análise da solicitação e seleção do fluxo;
- busca de trechos nos documentos selecionados, quando executada;
- preparação da conferência jurídica e consulta às fontes oficiais, quando executadas;
- consulta a dados autorizados, quando executada;
- espera pelo modelo e geração da resposta;
- conferência da resposta e suas referências;
- redação e gravação da conversa.

As etapas não avançam por temporizadores. O indicador não representa pensamentos internos do modelo nem afirma pesquisa jurisprudencial indisponível. Consultas jurídicas sem os dados necessários continuam solicitando esclarecimentos, sem anunciar uma consulta às fontes que não ocorreu. Trechos documentais e os limites de confirmação jurídica permanecem sob os controles anteriores.

O servidor envia eventos SSE `moara_progress` apenas no endpoint nativo `/moara/api/v1/chat/stream`, iniciando o fluxo antes das esperas de recuperação, conferência e inferência. Mensagens e metadados finais continuam no formato existente. Erros anteriores à abertura do fluxo preservam o status HTTP; falhas posteriores são eventos de erro com código e status de aplicação. As APIs de conclusão compatíveis continuam com seu contrato anterior.

O transporte mantém uma fila limitada, pressão de retorno, comentários periódicos de conexão e cancelamento da operação em andamento ao interromper o fluxo. O botão Interromper continua disponível, sem inserir os textos de status no histórico da conversa. A animação é desativada quando o navegador informa preferência por redução de movimento. O status usa anúncio acessível e as abas acomodam o texto ampliado.

## Validação e implantação

- 68 testes do backend aprovados, incluindo entrega de uma etapa antes de uma operação demorada terminar, cancelamento, preservação de erros e rejeição de etapas desconhecidas.
- Chromium isolado, com sessão real autorizada: coluna à direita, teclado, marca animada, busca documental, geração na GPU, citações, consulta legislativa, limites jurídicos, encerramento do status, interrupção, tela pequena, texto ampliado e redução de movimento.
- A versão pública foi testada sem interceptação do tráfego, confirmando que o status do servidor aparece antes da resposta. O proxy usado no teste privado pode agrupar o fluxo; esse teste valida a sequência, não a latência visual de cada evento.
- Recursos e conversas sintéticos foram arquivados; sessões nativas de teste foram revogadas.
- Evidências no servidor: `docs/runtime/work-progress-stage.json`, `work-progress-ui.json`, `work-progress-rail.png`, `work-progress-processing.png`, `work-progress-mobile.png`.
- Imagem ativa: `moara-core:work-progress-20261030`, com `work-progress-compose.yml` ao final do wrapper.
- A alteração preserva a entrada principal e o acesso ao chat anterior. Não há mudança de esquema de banco nem reinicialização dos serviços de inferência.

## Preservação e recuperação

Backup cifrado `moara-before-migration-20261030T224101Z.tar.enc`, com restauração isolada verificada em 30/10/2026 às 18:42:28, horário de Manaus. A imagem anterior está preservada como `moara-core:pre-work-progress-20261030`; o wrapper anterior está em `backups/work-progress-20261030/compose-before`.

Para reverter somente esta entrega, restaurar esse wrapper com modo 755 e executar `sh moara/infrastructure/scripts/compose.sh up -d --no-deps moara-gateway`. Conferir a prontidão e os dois acessos ao chat. Não executar `compose down` nem remover volumes, arquivos, modelos ou históricos. Os candidatos privados são interrompidos e preservados após a validação.
