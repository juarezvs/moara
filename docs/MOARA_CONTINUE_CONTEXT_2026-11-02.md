# Continuidade de contexto no Continue

O erro `Message exceeds context limit` nesta estação vinha da compilação local do Continue: a mensagem atual, as ferramentas e o último resultado já não cabiam no orçamento de 4096 tokens. A sessão analisada tinha 517 mensagens e repetia principalmente `ls` e `read_file`. A retirada anterior da cota por minuto não resolve esse limite distinto.

O modelo servido continua Gemma 4 12B, com contexto real de 8192 tokens. A configuração local agora anuncia 6144 tokens ao Continue e até 2048 tokens de saída. O orçamento enviado considera também o espaço das instruções acrescentadas pelo servidor; não se anuncia uma janela maior que a suportada pelo runtime.

Foi instalado um ajuste local, específico para `Continue.continue` 2.0.0 e `model: moara-code`, na função de compilação da requisição. Ele limita o pacote enviado a aproximadamente 12 KB antes das instruções do servidor, com:

- pedido original e orientação mais recente do usuário preservados;
- recibos das operações e chamadas/resultados recentes mantidos em pares válidos;
- argumentos extensos de operações passadas e saídas grandes representados como trechos explicitamente identificados;
- recuperação pelo plano `.moara/plano.md`, sem exigir que um plano já lido recentemente seja relido a cada chamada.

O histórico salvo e os arquivos do projeto não são reescritos por essa compactação. Ela não executa ferramentas, não usa uma segunda IA e não acrescenta chamadas de inferência para resumir. Não afirma que uma operação deu certo apenas porque há um recibo. As instruções do agente foram ajustadas para avançar a implementação em vez de reiniciar repetidamente as leituras.

Validação: nove testes automatizados aprovados, incluindo histórico longo, preservação de mensagens do usuário, saídas extensas e integridade dos IDs de ferramentas. Reprodução da sessão real: 518 mensagens de entrada contando o sistema, 315939 bytes; pacote compactado com oito mensagens e 11764 bytes. A API real aceitou o pacote com HTTP 200, contexto de 8192 e saída de 2048 preservada, retornando uma chamada nativa de ferramenta. O total após as instruções do servidor foi 17147 bytes. A chamada de ferramenta dessa reprodução foi inspecionada, não executada.

Instalação reproduzível e testes em `infrastructure/continue-autonomy/context/`. O instalador preserva o bundle original antes da alteração e recusa outra versão do Continue. A cópia instalada fica em `%USERPROFILE%/.vscode/extensions/continue.continue-2.0.0-win32-x64/out/moara-context.cjs`.

É necessário recarregar a janela do VS Code uma vez para carregar o novo código da extensão. A atualização do Continue pode substituir o bundle; por ser uma integração local, ela deve ser revalidada antes de reaplicar em outra versão. O patch é limitado a `moara-code`, sem alterar a compilação de outros modelos.

Não existe contexto infinito: um pedido individual enorme ou um catálogo de ferramentas que sozinho exceda a capacidade ainda exige arquivos ou partes menores. A compactação evita o crescimento ilimitado do histórico enviado, mas não garante a correção de qualquer projeto ou impede erros de código, Docker, rede e hardware.
