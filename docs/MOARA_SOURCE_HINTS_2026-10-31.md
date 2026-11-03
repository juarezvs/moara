# Fontes junto aos trechos — 31/10/2026

As respostas jurídicas novas incluem links junto aos trechos fundamentados: dispositivos legislativos usam seu identificador e informações dos temas do STF apontam para o cadastro ou para os andamentos correspondentes. Os links permanecem utilizáveis na exportação Markdown e na API.

A interface apresenta um pequeno painel ao passar o mouse ou focar a indicação de fonte. O painel permanece aberto durante o deslocamento do ponteiro para seu conteúdo e oferece **Abrir fonte oficial**, em nova aba com `noopener noreferrer`. Enter/toque abre o painel; Escape, o botão de fechar ou um clique fora o fecha. A posição é limitada à tela; o painel usa a camada superior do navegador para evitar recorte por áreas de rolagem.

Nas conversas salvas, referências como `[L1.1]` e `[J1.1]` são associadas aos links oficiais disponíveis na mesma resposta. Não são inventados endereços quando a associação não existe. Blocos de código não são transformados. Fontes documentais internas e links de evidências continuam com seu destino original.

O destaque visual se restringe a HTTPS e a uma lista explícita de domínios oficiais utilizados pelos conectores. A aplicação mantém DOMPurify e a sanitização do Angular, sem `bypassSecurityTrustHtml`. A aparência de fonte externa não constitui certificado de vigência, eficácia ou autenticidade de uma afirmação: permanece a conferência jurídica controlada pela aplicação.

## Validação

- Compilação Angular em produção e 163 testes unitários do backend.
- Navegador real: fonte junto à citação, mesmo URL no painel, ponteiro, teclado/Escape, toque/fechamento e tela de 390 px.
- Conversa sintética persistida: referência antiga, preservação de código, bloqueio de domínio semelhante ao oficial e sanitização de scripts/URLs executáveis.
- A regressão ampla também verificou os controles do painel com uma resposta real do STF. Uma consulta posterior ao STF pelo usuário restrito sofreu indisponibilidade da fonte; por isso os testes específicos da interface usam uma conversa sintética identificada, sem depender da disponibilidade externa.

Relatórios específicos: `docs/runtime/citations-ui-stage.json` e `citations-ui-public.json`. Capturas sanitizadas: `citations-desktop.png` e `citations-mobile.png`.

## Implantação e reversão

Imagem `moara-core:citations-v2-20261031`, base preservada `moara-core:pre-citations-20261031`, sobreposição `moara/infrastructure/citations-v2-compose.yml`. Somente o gateway é atualizado. MCP 0.7.0, inferência, proxy e dados permanecem nos serviços existentes.

O wrapper anterior fica em `backups/citations-v2-20261031/compose-before` (retorno ? primeira vers?o do painel) e `backups/citations-20261031/compose-before` (retorno ? vers?o anterior ao painel). Para reverter, restaurá-lo e executar `up -d --no-deps moara-gateway` pelo wrapper, verificando `/api/v1/ready`. Não excluir volumes.
