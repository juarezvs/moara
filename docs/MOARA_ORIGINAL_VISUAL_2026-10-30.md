# Identidade visual original no ambiente de trabalho

O ambiente em https://moara.am.trf1.gov.br/ foi adaptado à identidade visual original fornecida pelo usuário, preservando os recursos institucionais já implementados.

Foram reutilizados **os próprios arquivos** `brand/chat-bg.png` e `brand/mark.svg` existentes no projeto: fundo azul com ondas e pontos, marca M em azul/ciano/violeta, lateral escura e painéis translúcidos. Não foi criado um novo logotipo nem substituída a identidade institucional.

## Interface e ações

- Navegação das seis áreas mantida em coluna à direita, com foco de teclado e seleção acessível.
- Lateral esquerda com histórico, dossiês e acesso à Central Moara. Links administrativos são exibidos pelas permissões existentes de órgãos/diretórios, conectores, modelos, contas e identidade.
- Campo de mensagem central antes dos cartões de contexto e sugestões, disponível na primeira tela do celular. Um único template de formulário atende a abertura e a conversa, evitando controles duplicados ou perda do estado de trabalho.
- Seletor central de assistente/modelo abre as opções reais existentes.
- Ícones vetoriais locais consistentes, sem bibliotecas externas adicionais.
- Seis sugestões funcionais: analisar documentos, conferir legislação, preparar minuta, organizar o gabinete, desenvolver solução e explorar dados institucionais. As ações abrem o formulário correto ou preparam instruções e o assistente correspondente; não executam tarefas automaticamente.
- Indicador M animado e etapas reais do processamento preservados, incluindo o botão Interromper.
- Tema claro e escuro, redução de movimento, alto contraste e texto ampliado mantidos. No alto contraste, o fundo ilustrado e as transições são removidos para leitura imediata.

Recursos não implementados, como gravação autônoma em sistemas oficiais, não receberam atalhos simulando disponibilidade. As permissões, a conferência jurídica, as fontes oficiais e os limites de conclusão continuam sob controle da aplicação.

## Validação

Compilação Angular com o lockfile existente. A imagem candidata deriva da imagem de produção e copia **somente `/app/web`**. A comparação dos arquivos de `gateway`, `legal_mcp`, `identity` e `assistants` nos contêineres confirmou backend idêntico, com o mesmo hash agregado; não houve troca de dependências, modelos ou configurações de inferência.

Testes com Chromium isolado e sessão autorizada: ativos originais, fundo aplicado, seis atalhos, rotas, opções de assistente/modelo, envio e indexação de documento fictício, resposta com citações na GPU, etapas SSE, consulta jurídica, limites de vigência, interrupção, teclado, celular sem rolagem horizontal, campo de mensagem inicialmente visível, alto contraste e redução de movimento. Conversas e recursos sintéticos são arquivados e sessões nativas de teste revogadas.

Os registros visuais da lateral são mascarados nos testes para não expor nomes, dossiês ou históricos reais. Evidências no servidor em `docs/runtime/brand-stage.json`, `brand-ui.json`, `brand-backend-preservation.json`, `brand-http.json` e capturas `brand-desktop.png`, `brand-dark.png`, `brand-mobile.png`, `brand-processing.png`.

## Operação e recuperação

Imagem do frontend/core: `moara-core:brand-20261030`, overlay final `moara/infrastructure/brand-compose.yml`. Somente `moara-gateway` é recriado. O MCP permanece na imagem `moara-core:legal-sources-v2-20261030`, versão 0.2.0. Não houve migração de banco, alteração de Caddy ou reinicialização da inferência.

Backup cifrado `moara-before-migration-20261030T231632Z.tar.enc`, com restauração isolada conferida em 30/10/2026 às 19:18:03, horário de Manaus. A imagem core anterior foi preservada como `moara-core:pre-brand-20261030`; o wrapper anterior fica em `backups/brand-20261030/compose-before`.

Para reverter somente a apresentação, restaurar esse wrapper com modo 755 e executar `sh moara/infrastructure/scripts/compose.sh up -d --no-deps moara-gateway`. Verificar prontidão, entrada principal, login e chat. Os dados e as configurações institucionais permanecem nos volumes existentes. Não executar `compose down` nem remover históricos, evidências ou modelos.
