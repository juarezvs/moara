# Fundo do chat

O chat utiliza agora o mesmo fundo de /moara/: imagem original, gradiente de sobreposição, posicionamento, escala e comportamento de rolagem. As camadas opacas do modo de chat foram removidas para mostrar o fundo compartilhado da aplicação. Campos, navegação e respostas mantêm suas próprias superfícies para leitura.

Validação no navegador autenticado: página de referência e chat, temas claro/escuro, celular, alto contraste, botão Contexto e envio real de mensagem. Capturas e resultados ficam em docs/runtime/chat-background-*.json e background-chat-*.png.

Os 88 módulos Python, o logotipo e a imagem original permanecem idênticos. Apenas o frontend foi reconstruído. O overlay moara/infrastructure/chat-background-compose.yml altera somente a imagem do gateway; MCP, inferência e dados não são migrados ou reiniciados. O wrapper anterior e a imagem base estão preservados em backups/chat-background-20261102/compose-before e moara-core:pre-chat-background-app-20261102.
