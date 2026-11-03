# Moara — rolagem durante a resposta

Ao enviar uma pergunta ou gerar novamente uma resposta, a interface posiciona a conversa para mostrar o indicador de processamento. Na chegada do primeiro conteúdo, posiciona o início da resposta abaixo do cabeçalho. Ao terminar de salvar, ajusta novamente o início quando necessário, sem acompanhar cada trecho recebido.

Se o usuário começar a ler e rolar durante a geração, a conclusão não puxa a tela de volta. Gestos de roda, toque, teclado e interação com a conversa suspendem esse reposicionamento final. A rolagem é de posição, sem animação obrigatória, sem mover o foco e sem alterar o conteúdo das mensagens.

O ajuste considera o contêiner interno de mensagens no desktop e a rolagem da página no celular. Callbacks pendentes são invalidados na destruição da tela. Interrupção preserva o texto parcial. Consultas a dados autorizados também usam o mesmo posicionamento de início.

## Validação

Os relatórios `docs/runtime/chat-scroll-*.json` identificam a imagem exata e os resultados em homologação e na URL pública. Os cenários de rolagem usam streams controlados, marcados como sintéticos, com autenticação e persistência nativas reais. Verificam indicador visível, início da resposta, ausência de acompanhamento por fragmento, leitura manual, conclusão, próxima pergunta, regeneração, interrupção e celular. Os chats sintéticos são arquivados ao final.

Uma segunda verificação usa a conversa real sobre os temas de medicamentos de alto custo no STF, conservando tabelas, fontes, hints, cópia, expansão e larguras de leitura. A comparação do backend e a verificação dos serviços confirmam a preservação do MCP, dos catálogos, do timer e do modelo residente. Não há mudança de inferência, permissões ou banco.

## Implantação e reversão

Imagem `moara-core:chat-scroll-20261101`, overlay `moara/infrastructure/chat-scroll-compose.yml`. Somente o gateway é recriado, com prontidão verificada. A imagem anterior é preservada em `moara-core:pre-chat-scroll-app-20261101` e o wrapper anterior em `backups/chat-scroll-20261101/compose-before`. A reversão restaura esse wrapper e executa o compose somente do gateway, com `--no-deps`.

## Resultado publicado

Imagem validada: `sha256:1d2db19f43a7ef705102da9f57771a6dd396e6a0a69d0024d5323b4c56babf89`. Passaram, em homologação e na aplicação pública, 15 verificações de rolagem com streams controlados, 12 verificações da conversa real e 7 verificações de preservação. Os ambientes privados de teste foram parados e preservados. O MCP permaneceu com a mesma imagem e os modelos continuaram residentes.
