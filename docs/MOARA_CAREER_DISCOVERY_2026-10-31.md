# Identificação da lei de carreiras — 31/10/2026

A pergunta `qual a lei de cargos e salários do judiciário federal?` foi reproduzida na API real antes da alteração. O retorno anterior não identificou norma nem recuperou evidências suficientes. A busca literal e a reformulação anterior escolhiam normas antigas ou periféricas.

A descoberta agora traduz expressões de cargos e salários para termos de catálogo como carreiras, servidores e remuneração, preservando o empregador indicado. No contexto dessas carreiras, a expressão Judiciário federal também é pesquisada com a denominação Judiciário da União. As consultas originais são preservadas no diagnóstico. Não há associação de assunto a número de lei nem resposta fixa para esta pergunta.

Os resultados das consultas são combinados e classificados pelas ementas e referências oficiais. Falha em uma variante não descarta as demais. Para outros empregadores, os respectivos qualificadores são mantidos; perguntas sobre magistrados não são convertidas em carreiras de servidores.

O texto atualizado continua sendo recuperado a partir do vínculo no registro oficial da norma. A identificação e a ementa obtidas na Câmara agora apontam para esse registro realmente consultado, inclusive quando o Senado está indisponível. Não se atribui ao Senado conteúdo que veio exclusivamente da Câmara.

Perguntas que pedem identificar a lei podem usar diretamente a identificação oficial recuperada, inclusive após a etapa de recuperação. Isso evita uma longa reprodução de artigos ou a dependência de uma paráfrase do modelo para simplesmente informar o diploma encontrado. Outras perguntas, como penas, valores e requisitos, continuam a depender dos respectivos dispositivos.

## Resultado e validação

O teste da mesma pergunta identificou a [Lei nº 11.416/2006](https://www2.camara.leg.br/legin/fed/lei/2006/lei-11416-15-dezembro-2006-548306-normaatualizada-pl.html), que dispõe sobre as carreiras dos servidores do Poder Judiciário da União, com fontes e evidências reproduzíveis. A resposta delimita o objeto aos servidores; não apresenta valores de remuneração não solicitados nem certifica integralmente vigência ou efeitos judiciais.

- 179 testes unitários, incluindo uma norma fictícia de número arbitrário para demonstrar que a descoberta depende do catálogo, não de um mapeamento para 11.416.
- API real: mesma pergunta, identificação, fonte, escopo, evidências e resposta direta.
- Navegador real: pergunta exata, resposta, fonte oficial, painel de fonte, evidência e ausência de erros JavaScript.
- Regressão de identificação do CTB e critérios do diálogo competitivo.

Relatórios `docs/runtime/careers-*.json`; captura sanitizada `docs/runtime/careers-chat.png`. A identificação no ambiente de validação levou aproximadamente 8 segundos; não é garantia de tempo para todas as consultas.

## Operação

MCP 0.8.1 e imagem `moara-core:careers-20261031`. Somente gateway e MCP são atualizados pela sobreposição `moara/infrastructure/careers-compose.yml`. Inferência, navegador de descoberta, proxy e banco não são reiniciados nem migrados. A condição de acesso restrito do Google permanece explícita; esta correção usa fontes oficiais sem depender do Google.

Reversão: restaurar `backups/careers-20261031/compose-before` no wrapper e executar `up -d --no-deps moara-legal-mcp moara-gateway`, verificando as rotas de saúde. As imagens anteriores estão em `moara-core:pre-careers-mcp-20261031` e `moara-core:pre-careers-app-20261031`. Não apagar volumes.
