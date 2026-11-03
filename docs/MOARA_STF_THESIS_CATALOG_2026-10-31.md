# Acervo de teses do STF — coleta de 31/10/2026

Foram importados os dois bancos oficiais disponibilizados em [Teses de Repercussão Geral](https://portal.stf.jus.br/repercussaogeral/teses.asp): **819 registros com repercussão geral e 473 sem repercussão geral**, totalizando **1.292 registros e 1.292 números de tema distintos**. Não houve sobreposição de números entre os bancos nesta coleta.

## Método e cobertura

O JavaScript público da página (`/scripts/tesesrepercussaogeral.js`) mostra que cada banco completo é recuperado por POST ao serviço `retornartesesrepercussaogeral.asp`, com `tipo=com` ou `tipo=sem`. A paginação é feita no navegador por `array.slice`. O coletor usa o mesmo serviço público, com uma chamada para cada banco, em vez de repetir requisições para cada página visual. Não foi necessário contornar paginação, autenticação ou proteção do STF.

Antes da coleta, foi consultado `robots.txt`. O coletor usa identificação própria, TLS válido, intervalo entre solicitações e limites de resposta. Não visita `/processos`, rota desautorizada pelas instruções observadas. São preservadas cópias da página, do script, das instruções de acesso e das duas respostas completas.

O corpus contém o texto das teses divulgado nesses bancos, número do tema, paradigma, classificação, data de andamento mostrada pelo STF e links oficiais. A classe do paradigma (`RE` ou `ARE`) é preservada ao construir os links, sem converter todos os processos em RE. O link de acórdão é uma **pesquisa de acórdãos**, não confirmação de documento publicado ou coleta de seu inteiro teor.

O STF informa que as teses podem ser divulgadas antes da publicação dos acórdãos. Temas com mérito pendente podem não constar desses bancos. A classificação sem repercussão geral não é apresentada como tese de mérito constitucional. Não se certificam recursos, trânsito em julgado, modulação ou aplicabilidade a um caso apenas pelo conteúdo do catálogo.

## Persistência e consulta na Moara

O acervo fica em `data/legal/stf-theses`, com versões imutáveis, manifestos, cópias comprimidas e hashes SHA-256. O ponteiro `CURRENT` só é substituído depois de ambos os bancos terem sido validados, indexados e gravados. Uma falha parcial mantém a versão completa anterior.

Cada registro é pesquisável por texto e número do tema, com filtros dos dois bancos e paginação. A implementação usa um índice textual SQLite FTS5 local; não houve treinamento dos pesos do modelo nem nova carga de modelos na GPU. Os dados são públicos e ficam separados dos documentos institucionais e dos históricos pessoais.

- Interface: `/moara/chat?area=referencias&catalogo=stf`, em **Referências → Acervo STF**.
- API autenticada com `chat.use`: `/moara/api/v1/legal/stf-theses`.
- Exportação completa, incluindo cópias e hashes: `/moara/api/v1/legal/stf-theses/export`.
- MCP: `search_stf_thesis_catalog`, que informa explicitamente data da coleta e ausência de nova conferência online.

O catálogo também auxilia a descoberta de candidatos quando a pesquisa de temas por assunto no STF não retorna referências. Nesse caminho, os identificadores encontrados são novamente conferidos nas fontes oficiais pelo fluxo jurídico existente. A tese armazenada não é usada silenciosamente como prova de situação processual atual. O botão **Preparar conferência no chat** prepara uma consulta para revisão e envio, sem enviar todo o catálogo ao modelo.

O acervo público está disponível aos usuários autorizados ao chat. Não concede acesso a documentos, fontes institucionais, módulos administrativos ou dados de outras contas.

## Atualização e operação

A coleta desta entrega é uma versão datada, não uma promessa de sincronização instantânea. Para nova coleta, executar no servidor de aplicação:

```sh
cd /home/nutec/ai-server
python3 infrastructure/legal/harvest_stf_theses.py
```

O trabalho de importação é executado em contêiner temporário com raiz somente leitura, sem credenciais institucionais nem acesso ao banco. Apenas o diretório do catálogo recebe acesso de escrita. O ambiente Docker é rootless; o UID 0 do trabalho corresponde ao usuário proprietário do diretório no host. Gateway e MCP montam o acervo em modo somente leitura.

Não foi instalado agendamento automático nesta entrega. Novas versões completas são percebidas nas consultas seguintes sem reiniciar a GPU. Os históricos anteriores de coleta não são apagados.

## Validação

- 185 testes unitários, incluindo paginação, classificação, integridade, classes processuais, limites da fotografia local, falha de atualização parcial e conferência online obrigatória de candidatos.
- API real: todas as páginas, sem perda nem duplicação dos 1.292 registros.
- Comparação de cada registro exportado com as respostas oficiais originais e verificação dos hashes das cópias.
- Navegador real: filtros com/sem repercussão, busca textual, tema exato, fontes oficiais, download completo, celular e preparação da consulta no chat.

Os relatórios ficam em `docs/runtime/stf-harvest.json` e `stf-catalog-*.json`; capturas sanitizadas em `stf-catalog-desktop.png` e `stf-catalog-mobile.png`.

## Implantação e reversão

MCP 0.9.0, imagem `moara-core:stf-catalog-20261031`, sobreposição `moara/infrastructure/stf-catalog-compose.yml`. Atualizados apenas gateway e MCP. Não há migração de banco nem reinicialização de inferência, navegador de descoberta ou proxy.

O wrapper anterior está em `backups/stf-catalog-20261031/compose-before`. As imagens anteriores são `moara-core:pre-stf-catalog-app-20261031` e `moara-core:pre-stf-catalog-mcp-20261031`. Reversão: restaurar o wrapper, executar `up -d --no-deps moara-legal-mcp moara-gateway` por ele e conferir as rotas de saúde. Preservar o diretório de dados e os volumes.
