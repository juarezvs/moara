# Conferência jurídica da Moara — primeira versão em produção

## Estado real da entrega

Em 30/10/2026 foi publicada a **consulta documental inicial**, com servidor MCP
privado, etapa de conferência na aplicação e evidências protegidas. A aplicação,
o banco e as evidências ficam no servidor 172.19.5.250; a IA continua no computador
GPU 172.19.5.246. Os serviços de inferência e de embeddings existentes foram
preservados.

**A confirmação automática completa de vigência e eficácia ainda não está
implementada.** Esta versão distingue cronologia textual de vigência, mostra
as lacunas e suspende a análise conclusiva. Não há caminho que libere uma opinião
jurídica a partir de uma suposta certificação automática nesta versão.

## Uso

No [chat da Moara](https://moara.am.trf1.gov.br/moara/chat), informar, por exemplo:

> Confira o CPC, art. 12; data de referência: 2020-01-01.

Pode-se usar “hoje” para a data atual em Manaus. A data da própria lei não é
presumida como data dos fatos. Sem norma/data a aplicação pede esclarecimento.
Para evitar associação indevida de dispositivos, a consulta em linguagem natural
pede uma norma por vez quando encontra várias normas e artigos.

A resposta exibe trechos, data textual, fontes e limitações. O link **Consultar
evidências e fontes** abre um registro privado e permite baixar o pacote completo.
A abertura pelo chat nativo usa a sessão da própria Moara. Clientes que utilizam
somente Bearer devem enviar sua autenticação ao endpoint de evidências.

## Cobertura verificada e limites

| Fonte | Implementado | Limite |
|---|---|---|
| Senado / dados abertos | Identificação federal, publicações informadas, alterações e anotações por dispositivo | Metadados não certificam vigência ou ausência de eventos posteriores |
| normas.leg.br | Texto estruturado e versões por dispositivo quando disponíveis | A data de versão pode anteceder publicação/entrada em vigor; acervo estruturado incompleto |
| Planalto | Tentativa de consultar caminhos conhecidos de leis federais, com registro do resultado | Conexão recusada nos testes; nenhum contorno de bloqueio foi aplicado |
| DOU | Consulta oficial e recuperação de resultados quando acessíveis pelo servidor | Resultados podem apenas mencionar a lei; não há certificação das publicações, paginação completa, extras ou suplementos |
| STF | Referências constitucionais presentes no Senado; consulta da página anotada indicada para art. 27 da Lei 9.868/1999 | Inteiro teor, embargos, trânsito e modulação não estão confirmados automaticamente; página anotada pode estar desatualizada |

Nos testes reais, o CPC possui texto estruturado e o art. 12 apresenta redações
distintas antes/depois da alteração de 2016. A Lei 9.868/1999 retornou metadados,
mas não articulado estruturado; isso resultou em **não confirmação**, sem inventar
ou reutilizar uma redação corrente como histórica. O art. 9 do CPC apresentou
referências constitucionais. Essas referências não determinam, sozinhas, os
efeitos temporais de uma decisão.

Normas estaduais/municipais, pesquisa temática ampla, identificação jurídica
automática de todas as normas incidentes, regras de transição, datas de eficácia
e pesquisa jurisprudencial exaustiva permanecem fora da certificação automática.

## Controle pela aplicação e uso da IA

- `legal.draft` e agente `legal` passam obrigatoriamente pelo preflight antes de
  redigir ou consultar documentos. Assistentes e consultas documentais passam
  também pelo ponto central de completion.
- O chat detecta pedidos jurídicos por referências e termos; essa detecção é
  heurística e **não garante reconhecer toda pergunta jurídica implícita**.
  Os fluxos jurídicos explícitos são obrigatórios independentemente dessa
  heurística. `tools`, `tool_choice`, JSON e instruções do cliente não os dispensam.
- A IA recebe os trechos encontrados para uma seleção de até quatro IDs
  existentes. A aplicação valida esses IDs e descarta texto livre/IDs inventados.
  Essa seleção utiliza o perfil principal autorizado, com limite de 30 segundos.
  O conteúdo do caso não decide o roteamento para modelos de programação.
- A seleção da IA não autoriza conclusão sobre vigência. O relatório de limites
  e os trechos oficiais são montados pela aplicação. Falha dessa seleção preserva
  as evidências; falha das fontes não se transforma em confirmação.
- Não são enviados fatos ou documentos privados às fontes externas: apenas
  identificadores de normas. O processamento pela IA usa a infraestrutura local
  já autorizada da Moara.

## Evidências e reprodução

Migrações aditivas `0006_legal_evidence` e `0007_legal_evidence_guard` criam o
arquivo de evidências. O manifesto criptografado inclui solicitação, data do caso,
fontes, trechos, versões, alterações, anotações, tentativas de consulta e seleção
feita pela IA. As respostas oficiais bem-sucedidas são preservadas como bytes
comprimidos, hash SHA-256 e horário UTC da coleta. Não se utiliza cache antigo
como consulta recém-confirmada.

`GET /moara/api/v1/legal/evidence/{uuid}` exige `chat.use`, proprietário e
restrição da chave que originou o registro. A versão HTML facilita revisão; JSON
omite cópias volumosas por padrão. `?download=true` exporta o pacote completo.
O serviço verifica o hash do manifesto antes da leitura. Consultar um registro
antigo não atualiza sua data de conferência.

A conta de execução tem apenas SELECT/INSERT na tabela: UPDATE, DELETE e
TRUNCATE estão revogados; gatilhos bloqueiam mutação. Isso é preservação no
ambiente operacional, não carimbo do tempo externo, prova de autenticidade
governamental nem impossibilidade de intervenção por um administrador do banco.
Reproduzem-se as evidências documentais; não se promete saída idêntica de uma IA.

## MCP e operação

Serviço `moara-legal-mcp:8076`, sem porta publicada, redes `moara_control` e saída
dedicada `moara_legal_egress`. Sem credenciais de banco, volumes de documentos ou
acesso ao armazenamento da aplicação. Sistema de arquivos somente leitura,
capacidades removidas, limite de memória e concorrência HTTP de duas consultas.

Transporte HTTP stateless, JSON-RPC, versão MCP **2025-11-25**, `initialize`,
`ping`, `tools/list`, `tools/call` e notificações de inicialização/cancelamento.
Ferramenta: `verify_legal_sources`; argumentos tipados de data e normas federais.
Bearer de serviço protegido em `moara_legal_key`; Origin externo recusado. Não
aceita URLs arbitrárias nem segue redirecionamentos. Protocolos MCP posteriores
não são anunciados como suportados.

Imagem publicada: `moara-core:legal-20261030`. Base de reversão preservada:
`moara-core:pre-legal-20261030`, que já inclui a integração GPU. A sobreposição
`moara/infrastructure/legal-compose.yml` está no wrapper normal de inicialização.
Rebuild específico, no servidor e após compilar o frontend existente:

```sh
python3 infrastructure/legal/build.py
sh moara/infrastructure/scripts/compose.sh run --rm --interactive=false --no-deps moara-migrate
sh moara/infrastructure/scripts/compose.sh up -d --no-deps --no-build --pull never --wait moara-gateway moara-legal-mcp
```

Essa cópia local do repositório é parcial; a instalação usa os serviços e
dependências já existentes no servidor. Não contém os segredos operacionais.

Para reverter a funcionalidade mantendo a GPU, restaurar o wrapper guardado em
`backups/legal-20261030/compose.sh`, recriar somente `moara-gateway` com a imagem
GPU anterior e parar o novo MCP. Preservar as tabelas, backups e evidências; não
fazer downgrade destrutivo. O backup dos fontes e do frontend anterior está no
mesmo diretório. A migração aditiva não impede a execução da imagem anterior.

## Validação

- 16 testes automatizados: protocolo/autenticação, datas, seleção histórica,
  isolamento de artigos, SHA-256, recusa de redirecionamentos, indisponibilidade,
  tentativa de dispensar a etapa, ACL e validação da seleção feita pela IA.
- Testes na API da Moara: esclarecimento, duas datas do art. 12 do CPC,
  reprodução de todos os snapshots, integridade do manifesto, leitor HTML,
  data futura e SSE; chat comum continua na GPU.
- Agente jurídico executado em job real: pede esclarecimento mesmo quando a
  entrada não contém palavras jurídicas e não há documentos anexos.
- Teste real de privilégios: SELECT/INSERT permitidos; UPDATE/DELETE/TRUNCATE
  negados. Testes não alteraram dados de processos reais.
- Navegador isolado: envio no chat, aviso de vigência não confirmada, trechos,
  status, abertura privada das evidências e link de exportação; sem erros JS.
  Relatório renderizado em aproximadamente **7,8 segundos** no cenário sintético.
  A conversa sintética foi removida e a sessão de teste revogada.

Evidências sintéticas da execução ficam em `docs/runtime/moara-legal-*.json` e
capturas `moara-legal-chat.png` / `moara-legal-evidence.png` no servidor. Os registros
append-only de consultas sintéticas permanecem identificados como testes.

Fontes técnicas/oficiais: [Senado](https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html),
[normas.leg.br](https://normas.leg.br/),
[DOU](https://www.in.gov.br/consulta/-/buscar/dou),
[STF](https://portal.stf.jus.br/constituicao-supremo/leis-infraconstitucionais/verlegislacao.asp?item=346),
[MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
