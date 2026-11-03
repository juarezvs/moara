# Consultas informativas e limites de dispensa

Correção da exigência desnecessária de data em perguntas informativas, em 30/10/2026 (Manaus).

## Comportamento

Uma consulta como “me mostre o limite financeiro para dispensa de licitação previsto na lei 14133/2021” considera a data atual e informa essa escolha na resposta. Não depende de o usuário responder “hoje”. Perguntas sobre fatos, contratação concreta ou referências temporais ambíguas continuam exigindo esclarecimento. Uma norma ou pergunta nova não herda automaticamente uma data histórica de outro assunto da conversa. Datas inválidas não viram silenciosamente a data atual.

O MCP ganhou `consult_procurement_limits`, separado da análise jurídica conclusiva. Para os limites por valor do art. 75, I e II, a aplicação exige consulta oficial antes de responder. O modelo não cria valores nem decide se a consulta deve acontecer.

## Fontes e evidências

O conector lê pela rede, sem recuperação de cache antigo em caso de falha:

- Índice oficial de decretos do PNCP: https://www.gov.br/pncp/pt-br/pncp/legislacao/decretos.
- Tabela divulgada pelo Governo Federal: https://www.gov.br/compras/pt-br/acesso-a-informacao/comunicados/2025/no-47-25-decreto-altera-valores-da-lei-14-133-para-compras-publicas.
- Texto estruturado oficial da Lei 14.133/2021 no Senado/normas.leg.br, art. 75.

Confere identidade da lei, exercício explicitamente informado pela tabela, início em 1º de janeiro, ato de atualização compatível com o índice do PNCP e as duas linhas exatas dos incisos I e II. A lei é consultada para conferir o critério “valores inferiores”. Valores financeiros não estão fixados no código: são extraídos das linhas oficiais. Linhas ambíguas, duplicadas, ausentes, exercício incompatível, indisponibilidade ou divergência entre fontes impedem a apresentação de valores atuais.

A resposta informa os valores e as hipóteses, data de referência, decreto, fontes e horário da conferência. A evidência é gravada no armazenamento protegido já existente, com cópias comprimidas das fontes, SHA-256 e registro da escolha da data. O proprietário pode revisar o registro pela interface ou baixar o manifesto completo. A consulta informativa mantém `legal_conclusion_allowed=false`: não autoriza uma contratação concreta.

## Cobertura

O conector da tabela usa o comunicado oficial atualmente identificado, referente ao exercício de 2026. Se o PNCP passar a indicar outro ato ou o exercício mudar, o conector bloqueia essa tabela até ser identificada e integrada a nova fonte oficial. Não afirma cobertura futura automática nem consulta exaustiva de todos os atos do DOU. Sua indisponibilidade não permite reapresentar os valores originais da lei como atuais. A tabela corrente não é usada para estabelecer limites históricos ou futuros.

A correção geral de seleção de data também se aplica a outras perguntas informativas sobre normas identificadas; não transforma a cobertura parcial de vigência e jurisprudência em confirmação absoluta. A análise de casos permanece sujeita aos controles jurídicos existentes.

## Verificações e operação

100 testes automatizados, incluindo regressões do orçamento de contexto, seis assistentes, emissão de chaves para VS Code e novas verificações de data, tabela, ambiguidade, exercício, fontes indisponíveis e bloqueio de conclusões.

Testes reais pelo chat, com a pergunta exata relatada, conferência de três fontes oficiais, reprodução dos hashes e das cópias, evidência HTML/JSON e ausência de pergunta desnecessária de data. Pergunta de caso concreto continua pedindo data. Verificados também o FAQ de habilidades e a página de chaves do VS Code. Conversas sintéticas são arquivadas e sessões de teste revogadas.

Imagem de aplicação e MCP: `moara-core:legal-information-20261030`; MCP 0.3.0. Overlay final `moara/infrastructure/legal-information-compose.yml`. Não há migração de banco, mudança de modelos nem reinício da inferência.

Evidências no servidor: `docs/runtime/legal-information-stage.json`, `legal-information-public.json` e `legal-information-ui.json`. Scripts em `infrastructure/legal/`: `build_information.py`, `stage_information.py`, `live_information.py`, `run_browser_information.py` e `activate_information.py`.

A ativação exige backup com restauração verificada e validações do candidato. Para reverter, restaurar o wrapper salvo em `backups/legal-information-20261030/compose-before`, validar sua configuração e recriar somente `moara-legal-mcp` e `moara-gateway`. Preservar o banco e a auditoria; não executar `compose down`.
