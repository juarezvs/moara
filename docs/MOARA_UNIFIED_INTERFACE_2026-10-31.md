# Interface única da Moara

Implantação de 31/10/2026, America/Manaus.

O botão **Contexto**, com ícone de camadas, fica ao lado de **Opções**. Abre e recolhe o card **Contexto de trabalho**, inicialmente recolhido. O controle também está disponível durante a conversa. Recolher o painel preserva documentos selecionados, instruções e rascunho.

A raiz `/`, inclusive `/?interface=anterior`, encaminha para `/moara/chat`. Não existe mais uma segunda interface pública de chat. Os atalhos antigos encaminham para a interface atual; endereços de conversas antigas abrem o visualizador correspondente. O cabeçalho usa o símbolo original, azul institucional, detalhes ciano e violeta, identificação da Justiça Federal do Amazonas e controles de acessibilidade e tema, com adaptação para celular.

## Histórico e autenticação

O Histórico permite consultar as conversas anteriores, ativas e arquivadas, pertencentes à própria conta. A leitura e a exportação preservam o original. **Continuar em uma cópia** cria uma conversa nativa com o ramo de mensagens selecionado. Anexos e autorizações antigos não são transferidos automaticamente: documentos necessários devem passar pelas permissões da aplicação atual. Históricos grandes ou inconsistentes são sinalizados, sem truncamento silencioso.

O login atual aceita identificadores de diretório institucional e mantém a autoridade de autenticação existente. Verificação adicional, cadastro do autenticador e recuperação são apresentados na interface atual. A autenticação adicional não concede sessão antes da verificação. Não havia provedor OAuth configurado no inventário. As APIs existentes e seus controles permanecem disponíveis para os serviços dependentes.

## Validação e limites

- 119 testes automatizados de backend, incluindo isolamento de histórico, cópia criptografada, diretório e autenticação adicional.
- Verificação HTTP em ambiente isolado e na URL pública: raiz, atalhos antigos, páginas atuais e proteção de APIs anônimas.
- Navegador em desktop e celular: 21 verificações de identidade, contexto, preservação do rascunho e documentos, consulta e retomada do histórico, página de chaves e ausência de erros JavaScript.
- Compatibilidade pública da API para desenvolvimento validada com SDK e chave temporária, revogada ao fim do teste.
- Login de diretório e fatores adicionais validados por contrato e testes simulados; não foram usadas credenciais reais de diretório nem um autenticador pessoal.

Os dados sintéticos foram arquivados e as sessões de teste revogadas individualmente. Nenhuma conversa real foi excluída. Backup criptografado anterior à publicação teve restauração isolada verificada, incluindo integridade dos bancos e hashes dos arquivos. Candidatos isolados são parados e preservados após a validação.

## Operação e reversão

Imagem publicada: `moara-core:unified-20261031`. Overlay final: `moara/infrastructure/unified-compose.yml`. Base exata preservada: `moara-core:pre-unified-20261031`. Nenhuma migração de banco. Inferência e MCP não são reiniciados por esta implantação.

Configurações anteriores: `backups/unified-20261031/Caddyfile-before` e `compose-before`. Para reversão, restaurar o wrapper anterior, recriar somente `moara-gateway`, restaurar o conteúdo do Caddyfile preservando seu inode, validar a configuração e reiniciar somente o Caddy. Não executar `compose down` nem remover volumes. O script `infrastructure/site-entry/activate_unified.py` aplica validações prévias e reversão automática em caso de falha na ativação.

Evidências em `docs/runtime/`: `unified-ui-stage.json`, `unified-ui-public.json`, `unified-routes-stage.json`, `unified-routes-public.json`, `unified-ide-sdk-public.json` e `unified-final.json`. Capturas: `unified-desktop.png`, `unified-mobile.png` e `unified-dark.png`.
