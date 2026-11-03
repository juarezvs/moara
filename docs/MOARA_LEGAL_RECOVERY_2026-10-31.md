# Recuperação de fontes jurídicas e referências web

Correção de 31/10/2026. Pergunta usada na reprodução: “me explique como funciona e os critérios para usar a modalidade diálogo competitivo.”

## Problema e resultado

A consulta inicial não encontrava candidatas porque pesquisava uma expressão longa com palavras genéricas. Referências à lei-base com publicação em “1º de abril” também não eram reconhecidas. O seletor textual podia recuperar o caput e excluir incisos/alíneas que não repetiam os termos de busca.

A aplicação agora faz uma tentativa automática de recuperação pelo MCP antes de entregar uma resposta sem fontes. A recuperação reformula a expressão pública, consulta novamente o catálogo oficial e confere textos das normas. A pergunta original recuperou a Lei 14.133/2021, a definição do art. 6º e condições e procedimento do art. 32. O teste exige essas evidências e verifica seus hashes.

## Fluxo obrigatório

1. A consulta inicial e a tentativa de recuperação são controladas pela aplicação, não por uma decisão opcional do modelo.
2. A reformulação utiliza somente palavras já presentes nos termos públicos filtrados. Números de leis, pessoas ou fatos novos não podem ser inventados nessa etapa. Na ausência de reformulação válida, há uma redução determinística limitada dos termos.
3. O MCP repete a busca oficial com a expressão específica. Normas explicitamente informadas pelo usuário não são substituídas por outras sugeridas na busca.
4. Se não recuperar texto pertinente, o MCP pode consultar referências na web. Títulos, descrições e links retornados pelo buscador são pistas, nunca prova jurídica. Páginas de terceiros não são baixadas para fundamentar a análise.
5. Referências numéricas sugeridas pelas pistas voltam à verificação oficial. Links da Câmara podem levar ao texto atualizado, com identidade conferida, fonte aprovada e respeito à data relevante. Publicação original e cópia corrente não são usadas silenciosamente como redação histórica.
6. Textos recuperados precisam guardar relação com o assunto; resultados desconexos são rejeitados. Ementa de norma não relacionada não é aceita como recuperação do conteúdo necessário.
7. Consulta inicial, reformulação, tentativas, busca web quando utilizada, textos oficiais e cópias com SHA-256 ficam no registro de evidências do proprietário.

A interface mostra **“Ampliando a pesquisa e buscando referências para localizar fontes oficiais…”** durante essa etapa. Se todas as tentativas falharem, a resposta informa a lacuna e permite refinar o ponto, órgão ou endereço oficial.

## Condições legais e interpretação

Caput, incisos e alíneas relevantes são mantidos no contexto. Consultas sobre critérios/requisitos permitem mais dispositivos, ainda limitados. Em respostas recuperadas com condições complexas, a aplicação apresenta a redação oficial organizada e vinculada às fontes. Isso preserva conjunções e negações, sem transformar requisitos cumulativos em alternativas ou inverter uma expressão como “sem adaptação”.

O conteúdo recuperado orienta a resposta daquela análise e fica nas evidências; não há treinamento automático dos pesos do modelo ou incorporação indiscriminada de páginas à base institucional.

## Busca web e limites

MCP **0.6.0**, nova ferramenta privada `recover_legal_sources`. A busca web usa o RSS público do Bing, sem chave paga e apenas como mecanismo auxiliar. O endpoint não oferece contrato de disponibilidade equivalente a uma API contratada; pode falhar ou retornar resultados irrelevantes. Resultados sem relação com o assunto são descartados. CAPTCHA, bloqueio e indisponibilidade não são contornados.

O provedor de busca é separado do cliente de fontes normativas. Seu domínio não foi adicionado à lista de fontes oficiais de fundamentação. As respostas do buscador são limitadas em tamanho e tempo; XML com declarações de entidades é rejeitado. URLs privadas, portas indevidas, credenciais em URL e redirecionamentos arbitrários não habilitam leitura de conteúdo jurídico.

Só são enviados termos públicos filtrados ou identificadores normativos estruturados; o relato integral, anexos, credenciais e identificadores pessoais não são usados como consulta ao buscador. A filtragem e a redução não substituem controles de sigilo sobre a entrada institucional. Falha do próprio serviço MCP também pode impedir a recuperação e é registrada como indisponibilidade, sem afirmar que uma fonte foi consultada com sucesso.

Continuam válidas as limitações de cobertura federal, redação histórica, vigência, transição, constitucionalidade e efeitos judiciais. Uma busca sem resultado não comprova inexistência de norma. Citação literal válida não certifica todas as interpretações jurídicas possíveis.

## Verificação e operação

153 testes automatizados de backend, incluindo recuperação obrigatória após resultado vazio, reformulação sem termos inventados, dias ordinais, preservação de contexto dos requisitos, rejeição de pistas irrelevantes e de texto de buscador como fundamento, vínculo com compilação oficial, restrições de URL/data e preservação literal de condições.

Consultas reais no candidato isolado e na publicação: pergunta original sobre diálogo competitivo; identificação de normas de trânsito, proteção de dados e violência doméstica; explicação sobre promoção na Lei 8.112/1990. Teste de navegador envia a pergunta original, confere critérios e referências, e preserva regressão de contexto, histórico, login, RBAC e API do editor.

Imagem: `moara-core:legal-recovery-20261031`; overlay `moara/infrastructure/legal-recovery-compose.yml`. Bases exatas preservadas: `moara-core:pre-legal-recovery-20261031` e `moara-core:pre-mcp-recovery-20261031`. Sem migração de banco, alteração de AD/RBAC ou reinício dos modelos. Reversão: restaurar `backups/legal-recovery-20261031/compose-before` e recriar apenas gateway e MCP, preservando volumes e históricos.

Evidências em `docs/runtime/legal-recovery-stage.json`, `legal-recovery-public.json`, `legal-recovery-ui-stage.json`, `legal-recovery-ui-public.json`, `legal-recovery-sdk.json`, `legal-recovery-final.json` e `legal-recovery-chat.png`.
