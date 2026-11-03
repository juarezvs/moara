# Moara — interface institucional própria

## Direção visual

A interface de trabalho foi recomposta com uma hierarquia editorial própria: marca Moara no cabeçalho, navegação textual em uma lateral única, tela inicial alinhada à esquerda e um painel complementar de orientação. O fundo espacial, os efeitos de vidro, a marca repetida na abertura e a coluna de ícones à direita foram substituídos por superfícies sóbrias, divisórias discretas e conteúdo com mais espaço para leitura.

A paleta usa azul profundo, cinza claro e branco, com pequenos acentos associados à marca original. Os títulos de abertura adotam tipografia editorial; controles e conteúdo de trabalho mantêm tipografia de interface. O símbolo “M” e a identificação da Justiça Federal do Amazonas permanecem. Essa é uma mudança de composição e apresentação, sem pretensão de emitir uma avaliação jurídica sobre semelhança ou propriedade intelectual.

Os modos Conversar, Planejar e Minuta foram reposicionados no cabeçalho do compositor. Opções e Contexto continuam acessíveis junto à área de envio. As atividades frequentes aparecem como linhas de trabalho, sem a grade anterior de cartões. Administração e integrações foram agrupadas em uma seção expansível, respeitando as mesmas permissões de cada recurso.

## Navegação e leitura

- Desktop: navegação de áreas, histórico e dossiês à esquerda; conteúdo no centro; orientação complementar na abertura.
- Celular e tablet: menu de áreas com abertura explícita, foco contido enquanto aberto, fechamento por Escape, restauração do foco e fechamento ao selecionar uma área.
- Tema claro e escuro: superfícies e controles próprios para cada paleta, com revisão de contraste dos textos auxiliares e estados desabilitados.
- Conversa: permanecem a largura alinhada de pergunta e resposta, o processamento observável com a marca Moara, tabelas, fontes com hints, cópia e expansão das teses extensas.

Foram mantidos documentos, modelos, referências, acervos, histórico, dossiês, contexto, configurações de assistente e modelo, autenticação e links administrativos autorizados. A entrada pela raiz continua levando a `/moara/chat`.

## Implantação e evidências

A mudança é de frontend. A imagem parte da aplicação que estava em execução e acrescenta apenas o diretório web compilado. A comparação criptográfica dos 87 arquivos Python do backend confirma igualdade com a versão anterior. O serviço MCP e o servidor de inferência não são recriados. Catálogos, timer de coleta, permissões, dados e modelos residentes são preservados.

Os testes usam a aplicação real, sessões de teste isoladas e dados sintéticos arquivados ao final. A homologação cobre composição, navegação das seis áreas, modos, contexto, opções, links de administração, tema escuro, teclado, menu móvel, ausência de rolagem horizontal e envio real de mensagem. A regressão da conversa repete a pergunta sobre medicamentos de alto custo, incluindo os dois temas, fontes, tabela, expansão, cópia e leitura no celular.

Os relatórios `docs/runtime/institutional-*.json` identificam a imagem exata e os resultados em homologação e na URL pública. As imagens `institutional-home-desktop.png`, `institutional-home-dark.png`, `institutional-home-mobile.png` e `institutional-chat-*.png` são capturas verificadas com dados pessoais e histórico mascarados quando presentes.

## Operação e reversão

Imagem de frontend: `moara-core:institutional-ui-20261031`. Overlay: `moara/infrastructure/institutional-ui-compose.yml`. A publicação recria somente `moara-gateway`, com validação de prontidão e retorno automático ao wrapper anterior caso a inicialização falhe.

A imagem anterior está preservada em `moara-core:pre-institutional-ui-app-20261031`; o wrapper anterior fica em `backups/institutional-ui-20261031/compose-before`. A reversão restaura esse wrapper e executa o compose somente de `moara-gateway`, com `--no-deps`. Não é necessário alterar o Caddy, recriar banco, remover volumes ou reiniciar inferência e MCP.

## Resultado publicado

Imagem validada: `sha256:984ac563e8667d42035254d680ea42ffb5cc5d67aa43d237fc4125f06996f77d`. Passaram, em homologação e na URL pública, 22 verificações de interface, 12 verificações de conversa e 7 verificações de preservação, totalizando 41 verificações. O modelo principal e o modelo de embeddings continuaram residentes. Os ambientes privados de teste foram parados e preservados após a validação.
