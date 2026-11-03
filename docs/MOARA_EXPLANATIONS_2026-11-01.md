# Moara — explicações fundamentadas

A pergunta “me explique a diferença entre cessão e requisição de servidor” foi reproduzida antes da alteração. A resposta caía em `quoted_sources_fallback`, com uma lei incidental e artigos predominantemente remuneratórios, em vez de explicar os dois conceitos.

## Alterações

- A pesquisa distingue os termos do assunto das instruções de apresentação. Busca variantes de flexão e prioriza dispositivos conceituais, sem um mapa fixo de perguntas para números de leis.
- O catálogo registra a indicação oficial de revogação total. O ato revogador explicitamente vinculado serve como candidato de pesquisa, sujeito à conferência; não é automaticamente declarado substituto integral ou vigente.
- O fluxo diferencia explicar, comparar e identificar. Perguntas explicativas recebem texto em linguagem simples com referências junto aos parágrafos.
- A geração usa JSON Schema e identificadores restritos a passagens realmente recuperadas. As citações literais são montadas pela aplicação, sem exigir que o modelo as recopie.
- Uma revisão separada compara os parágrafos às evidências. Existe uma tentativa limitada de correção. Parágrafos adicionais rejeitados podem ser omitidos sem apagar a explicação sustentada; essa limitação fica explícita.
- Perguntas sobre critérios e requisitos conservam os dispositivos selecionados em um painel expansível, além da explicação. Assim, os incisos, exceções e relações cumulativas podem ser conferidos literalmente.
- Uma proteção de atribuição preserva o papel de requisitante/requisitado quando a própria passagem citada atribui inequivocamente o mesmo verbo ao outro papel. Não infere direitos ou prerrogativas. A correção fica registrada na evidência.
- Ajustes de contexto de tarefas internas estruturadas permanecem na auditoria e nos metadados, sem inserir prosa antes do JSON.

As verificações são controles de qualidade e proveniência, não prova formal de todas as interpretações. A consulta não certifica cobertura nacional integral, vigência histórica ou aplicabilidade individual. Falhas continuam identificadas como falhas, sem inventar conteúdo.

## Preservação e validação

Os 223 testes automatizados cobrem também as capacidades anteriores. A interface, seus 83 arquivos e a rolagem são idênticos à versão anterior. Os outros 83 módulos Python permanecem idênticos. Não há alteração de banco, identidade, RBAC, autenticação, integração com VS Code ou configuração de inferência.

Os testes reais usam a aplicação autenticada, o MCP e o modelo da GPU: comparação solicitada, promoção, diálogo competitivo, identificação da lei de carreiras e habilidades. Os relatórios com a imagem exata estão em `docs/runtime/explanation-*.json`; o fechamento da implantação está em `explanation-final.json`.

## Operação

Overlay: `moara/infrastructure/explanation-compose.yml`. A ativação valida relatórios e imagem, preserva o wrapper anterior em `backups/explanation-20261101/compose-before` e reinicia somente gateway e MCP. As imagens anteriores são preservadas como `moara-core:pre-explanation-app-20261101` e `moara-core:pre-explanation-mcp-20261101`.

Os catálogos permanecem montados somente para leitura. O modelo principal e o de embeddings permanecem residentes. A conferência final verifica o timer de metadados e interrompe somente os candidatos privados desta implantação, preservando-os para revisão.
