# Moara — ambiente de trabalho inspirado nas referências visuais

Endereço: **https://moara.am.trf1.gov.br/moara/chat**.

As telas enviadas do MinutaIA orientaram a organização: navegação por áreas,
histórico e dossiês na lateral, contexto central e barra de instruções inferior.
A identidade visual, os seis assistentes e as políticas institucionais da Moara
foram mantidos. Não houve integração com o serviço comercial.

## Funcionalidades

| Área | Comportamento |
|---|---|
| Início | Cinco entradas de contexto: documentos, modelos, legislação, jurisprudência e assistentes/instruções |
| Histórico | Filtro por título, retomada da conversa e suas fontes, arquivamento preservando mensagens; acesso ao histórico anterior |
| Documentos | Arrastar e soltar, seleção de múltiplos arquivos, texto colado transformado em documento, indexação e escolha de fontes |
| Modelos | Estruturas reutilizáveis do acervo autorizado, prévia e seleção para orientar um rascunho |
| Referências | Formulário de norma, dispositivo e data; conferência pelo fluxo jurídico existente, com evidências e lacunas explícitas |
| Acervo | Criar e utilizar instruções e modelos; criar dossiês que reúnem os documentos selecionados; escolher os seis assistentes |
| Editor | Editar uma cópia da resposta, salvar como documento e baixar Markdown, com indicação de rascunho para revisão humana |
| Opções | Assistente, modelo de execução autorizado, extensão da redação e consulta de dados somente de leitura |

**Modelos de documento** são estruturas textuais, diferentes dos **modelos de IA**
selecionados em Opções. Variáveis sem informação permanecem pendentes; escolher
uma estrutura não prova fatos nem confirma suas referências legais.

O conteúdo da estrutura aplicada, seu título e sua versão são incluídos na
mensagem gravada na conversa. A seleção de documentos continua sendo enviada ao
backend e validada antes da recuperação. Não se armazenam textos privados em
localStorage para implementar esse ambiente.

## Modos de trabalho

- **Conversar:** responder à tarefa com o contexto autorizado.
- **Planejar:** solicitar um roteiro de etapas e informações necessárias. A pessoa
  pode abri-lo no editor, revisá-lo e escolher **Usar roteiro na minuta**.
- **Minuta:** solicitar um rascunho para revisão humana. Um roteiro aceito aparece
  no contexto; gerar a minuta ainda exige o envio explícito das instruções.

São instruções de trabalho para o mesmo modelo principal. Não correspondem a
seis modelos, a um motor novo de raciocínio ou a uma pesquisa jurídica profunda
autônoma. A fila e o servidor GPU não foram alterados.

O botão **Novo trabalho** limpa o contexto e volta à seleção automática e ao
principal compartilhado. A resposta original da conversa não é substituída
pela edição manual. O arquivo salvo recebe identificação de RASCUNHO e fica
no armazenamento institucional existente; sua indexação posterior pode ser
solicitada no espaço de trabalho.

## Limites e estados verdadeiros

- Até 16 documentos no contexto; 4 MiB por arquivo. PDF, DOCX, XLSX, TXT, MD e
  CSV UTF-8 mantêm os formatos e limites do backend existente.
- OCR de PDFs permanece automático dentro dos limites existentes. Não há um
  interruptor visual simulando uma configuração que o backend não oferece.
- Texto de modelo limitado a 6.000 caracteres para aplicação no chat. O orçamento
  global de contexto continua validado pelo servidor e pode exigir redução.
- O acervo e os dossiês usam a autorização existente, sem compartilhamento
  automático ou ampliação de acesso por escolher um assistente.
- Pesquisa jurisprudencial ampla continua pendente. A área correspondente
  explica a cobertura inicial e prepara um pedido; não apresenta resultados
  fictícios ou confirmação automática de precedentes.
- PJe e SEI aparecem como preparados e aguardando mecanismo oficial homologado.
  A consulta jurídica obrigatória não pode ser desligada por esta interface.
- Salvar ou baixar um rascunho não assina, publica, tramita ou envia o texto a
  sistemas oficiais. O editor desta entrega exporta `.md`; os demais fluxos
  documentais existentes continuam no espaço de trabalho completo.

## Validação e implantação

A aplicação Angular foi compilada em produção com as dependências travadas.
O build da nova imagem copia somente os arquivos estáticos sobre a imagem exata
anterior; não há migração de banco nem troca de backend/modelo.

Em navegador real, a candidata privada passou por envio por arrastar e soltar,
texto inserido/indexado, modelo e instrução persistidos, resposta RAG com citações
na GPU, download e salvamento da cópia editada, preservação da resposta original,
dossiê com seleção restaurada e formulário jurídico com conclusão suspensa quando
a vigência não foi confirmada. Teclado, tela de 390 px, contraste e texto ampliado
também foram exercitados. Os testes usam apenas conteúdo sintético, arquivado
ao final; suas sessões são revogadas.

Após a publicação, **21 verificações pelo navegador passaram no HTTPS público**,
sem proxy da candidata e sem erros JavaScript. Foram confirmados os fluxos acima,
incluindo roteiro revisado antes da minuta. O rascunho documental com duas fontes
e estrutura selecionada apareceu em 6,16 s nesta amostra sintética; isso não é SLA.

Relatórios: `docs/runtime/workbench-ui.json` (`candidate_proxy:false`),
`workbench-plan.json` e `workbench-final-operation.json`. Ao encerrar, os 27
serviços estavam ativos, o transporte seguia em TLS mútuo e o principal e os
embeddings continuavam residentes em GPU. Candidatas privadas foram paradas,
mantendo containers e imagens.

Backup anterior à publicação: `moara-before-migration-20261030T170942Z.tar.enc`.
A restauração isolada foi verificada em 30/10/2026 17:11:12 UTC, com contagens,
hashes, configurações, SQLite e CA conferidos, sem modificar a produção.

Build: `python3 infrastructure/moara2/build_web.py`, seguido de
`python3 infrastructure/workbench/build.py`. A imagem é
`moara-core:workbench-20261030`, com overlay
`moara/infrastructure/workbench-compose.yml` ao final do wrapper Compose.

Reversão: imagem preservada `moara-core:pre-workbench-20261030` e wrapper em
`backups/workbench-20261030/compose-before`. Reverter apenas o gateway da Moara;
preservar banco, recursos e documentos criados durante o uso. Não há alteração
na residência GPU, nos pesos, nos certificados nem nos túneis de inferência.
