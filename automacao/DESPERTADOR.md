# Despertador (cron-job.org)

O agendador grátis do GitHub atrasa horas ou nem dispara. Quem manda é **uma tarefa só** no cron-job.org
(conta do Antônio): **Relógio**, a cada 15 minutos, que chama a tarefa `relogio` do GitHub.

A cada chamada o `relogio` faz o que já está na hora e ainda não saiu naquele dia:
- a partir das 6h: story de bom dia (depois do meio-dia, pula e avisa uma vez);
- a partir das 7h30: prévia do post do dia (próximo item do `banco/`) no Telegram;
- terça e quarta a partir das 15h: os 2 stories da promo;
- e lê o Telegram (botões Postar / Outra legenda / Descartar): resposta em até 15 min.

## Configuração da tarefa Relógio
- **URL:** `https://api.github.com/repos/antonioventuress-cell/moda-estampa-posts/actions/workflows/postagem.yml/dispatches`
- **Every 15 minutes**, time zone `America/Sao_Paulo`
- **POST**, headers `Authorization: Bearer <chave>`, `Accept: application/vnd.github+json`, `Content-Type: application/json`
- **Body:** `{"ref":"main","inputs":{"tarefa":"relogio"}}`

A chave é fine-grained (`moda-estampa-despertador`), só **Actions: Read and write** no repositório `moda-estampa-posts`,
e **vence em 25/01/2027**: gerar outra antes e trocar no header Authorization.

Pra recriar do zero: CREATE CRONJOB → IMPORT FROM CURL:
```
curl -X POST https://api.github.com/repos/antonioventuress-cell/moda-estampa-posts/actions/workflows/postagem.yml/dispatches -H "Authorization: Bearer COLE_A_CHAVE_AQUI" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" -d "{\"ref\":\"main\",\"inputs\":{\"tarefa\":\"relogio\"}}"
```
Teste: 204 = certo; 401 = chave errada/vencida; 422 = body diferente.
