# Minutas jurídicas com fontes e campos pendentes

## Problema reproduzido

O pedido de petição de aposentadoria para pescador segurado especial, inclusive com o texto acrescentado pelo modo Minuta, retornava uma pergunta genérica sobre data e assunto. O bloqueio ocorria antes da elaboração do documento.

A causa combinava a ausência de um caminho próprio para redação jurídica com a inclusão das instruções de apresentação na identificação do assunto. A recuperação genérica também encontrou normas sobre seguro-defeso e previdência de servidores, insuficientes para a petição solicitada.

## Correção

legal_drafting.py identifica pedidos de petição, requerimento, contestação e recurso. A aplicação distingue a pesquisa normativa necessária para elaborar um rascunho da confirmação dos fatos e da conclusão sobre o direito de uma pessoa.

Quando não há data informada, a data atual serve como referência da pesquisa preparatória, com o identificador current_date_for_draft_research_not_case. Ela não se transforma em DER, data de aquisição do direito ou data dos fatos. Datas históricas expressamente informadas continuam preservadas.

O documento contém endereçamento, qualificação, fatos, fundamentação, provas, pedidos, valor e fechamento. Os fatos não demonstrados ficam como campos pendentes. Na aposentadoria do pescador segurado especial, a estrutura por idade é uma hipótese explícita a confirmar; não se presume idade, período, requerimento, indeferimento ou satisfação dos requisitos.

Para esse assunto, a Lei 8.213/1991 é uma referência curada de pesquisa, e não uma resposta pronta: o MCP precisa recuperar o texto oficial e conferir sua identidade antes de utilizá-lo. A compilação da Câmara foi acrescentada como endereço alternativo de fonte. A enumeração de dispositivos orienta a consulta; somente os trechos efetivamente recuperados podem sustentar o texto.

A leitura do HTML foi corrigida para não interpretar referências internas minúsculas, como uma linha quebrada contendo “art. 2º da Lei…”, como início de um novo artigo. Esse erro cortava a passagem do art. 11 sobre pescador artesanal. A seleção para o modelo também preserva janelas literais próximas do conceito procurado em artigos longos.

## Fundamentação e revisão

A redação dos fundamentos usa identificadores de passagens existentes e passa pelas verificações de procedência e fidelidade. A revisão recebe o contexto dos dispositivos, além das citações isoladas, para distinguir benefícios, requisitos e exceções.

Foi acrescentada uma verificação da alternativa atividade individual/economia familiar: a segunda não pode ser apresentada como requisito universal quando a fonte admite ambas. Alegações individuais não comprovadas continuam vedadas.

Se uma tentativa de correção do modelo falhar, os argumentos que já passaram na revisão podem ser preservados, excluindo os rejeitados. Isso evita apagar toda a fundamentação válida por erro em um parágrafo suplementar. Uma falha integral de fontes ainda permite devolver a estrutura editável, com fundamentação explicitamente pendente, sem inventar artigos ou jurisprudência.

O botão Abrir no editor agora admite respostas identificadas pela aplicação como minutas jurídicas. As verificações, as permissões e o pipeline de Markdown permanecem ativos; a alteração não autoriza assinatura ou protocolo.

## Validação e evidências

Publicação concluída em 02/11/2026. Passaram 299 testes automatizados do backend/MCP, os 10 testes existentes do frontend e, tanto em homologação quanto em produção, 11 verificações pela API e 12 pelo navegador. A mesma pergunta retornou uma petição editável com fundamentação e fontes oficiais, em vez da solicitação genérica de data e assunto.

Foram incluídos testes de regressão para o pedido exato, instruções do portal, assuntos públicos sem identificadores pessoais, data histórica, falha das fontes, estrutura documental, rejeição de fatos inventados, leitura de referências internas, preservação de argumentos aprovados e alternativas legais.

O teste real pela API exige uma petição com fundamentação, fontes oficiais da Lei 8.213/1991 recuperadas, campos pendentes e evidências reproduzíveis. O teste no navegador utiliza o modo Minuta, acompanha o processamento e verifica citações, rolagem externa e edição do documento.

As 18 verificações de encerramento passaram, incluindo imagens publicadas iguais às testadas, modelos residentes, catálogos somente para leitura, preservação da atualização concorrente e dos arquivos de identidade visual. A comparação do CSS ativo identificou apenas a retirada da utilidade Tailwind .fixed, sem uso nos templates; a rolagem externa e o editor foram conferidos no portal.

- [API em homologação](runtime/legal-draft-live-stage.json)
- [API em produção](runtime/legal-draft-live-public.json)
- [Navegador em homologação](runtime/legal-draft-ui-stage.json)
- [Navegador em produção](runtime/legal-draft-ui-public.json)
- [Conferência final](runtime/legal-draft-final.json)
- [Exemplo de rascunho retornado em produção](runtime/legal-draft-example.md)

## Operação

O overlay legal-draft-compose.yml atualiza gateway e MCP sobre as imagens anteriores. Esta entrega não acrescenta migração de banco nem reinicia a inferência. Os catálogos oficiais continuam somente para leitura. Durante a validação, outra atualização introduziu ajustes nas chaves de API; a base foi atualizada para preservar auth.py, admin_api.py e a migração 010, com conferência dos hashes. O script de composição anterior fica em backups/legal-draft-20261102/compose-before; as imagens de retorno têm as tags pre-legal-draft-app-20261102-r2 e pre-legal-draft-mcp-20261102.
