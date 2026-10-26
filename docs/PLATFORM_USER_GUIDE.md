# Manual do espaço de trabalho

Abra a Moara e escolha **Espaço de trabalho** no menu. Cada item começa privado.
O compartilhamento permite leitura ao grupo selecionado; somente o proprietário
edita ou arquiva. Participar do grupo de um assistente não concede acesso aos
documentos usados por ele.

## Documentos e conhecimento

Selecione Documentos e envie PDF, DOCX, TXT, Markdown ou CSV de até 4 MiB.
CSV e texto devem estar em UTF-8. Após o upload, selecione **Indexar para
consulta** e acompanhe Execuções. Só documentos indexados participam da busca.

Digite a pergunta em Consultar conhecimento. A resposta aparece na execução,
acompanhada de referências ao documento e à página quando disponível. Se perder
acesso a uma fonte, a resposta correspondente também deixa de ser disponibilizada.
Digitalizações ruins podem exigir revisão do original e nova ingestão.

## Prompts, templates e assistentes

Prompts guardam instruções reutilizáveis. Em Templates, escreva campos como
{{nome}} e declare nome na lista de variáveis. Informe todos os valores e gere o
DOCX identificado como rascunho.

Assistentes combinam instruções com documentos selecionados. Use uma solicitação
clara; fontes indisponíveis para a sua conta não serão usadas.

## Indicadores e processos

Para Analytics, envie um CSV, escolha uma fonte, a coluna de agrupamento e
contagem, soma ou média. A saída inclui definição, hash da fonte e CSV exportado.
A API também permite filtros por igualdade; não executa SQL livre.

Em Processos, vincule documentos autorizados e registre eventos com data, fato e
fonte. Gere uma minuta pela solicitação. Confira fatos, citações, cálculos e
fundamentação antes de utilizar qualquer texto. A plataforma não assina nem
protocola atos judiciais.

## Desenvolvimento

Crie um projeto e descreva o resultado desejado. A Moara propõe arquivos, plano,
diff e revisão. A proposta não modifica os arquivos nem executa código sozinha.
Abra o resultado e aceite a proposta para criar uma nova versão.

Contas com permissão development.execute podem revisar os arquivos salvos e
aprovar aquela versão para execução. O ponto de entrada é main.py para Python
ou main.ts para TypeScript. O ambiente não instala dependências nem acessa rede,
credenciais ou arquivos corporativos. A saída e o código de encerramento ficam
em Execuções. Resultado concluído significa que a execução terminou, não que
os testes ou a revisão foram aprovados.

## Fluxos

A tela oferece um fluxo inicial de notificação simulada. A API aceita também
busca documental, template e agregação. Nenhuma notificação é enviada a pessoas.
Ative o agendamento e escolha um intervalo de pelo menos 300 segundos. Alterações
geram nova versão. Se o proprietário perder permissão, o agendamento deixa de
executar. Cancelamento é cooperativo e verificado durante os jobs.
