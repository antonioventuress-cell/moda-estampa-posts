# Despertador dos horários (cron-job.org)

O agendador grátis do GitHub atrasa horas ou nem dispara. O cron-job.org (grátis) aciona o GitHub no minuto certo.

## 1. Chave do GitHub
github.com → Settings → Developer settings → Fine-grained tokens → Generate new token
- Token name: `moda-estampa-despertador`
- Repository access: **Only select repositories** → `moda-estampa-posts`
- Permissions → Repository → **Actions: Read and write** (só essa)
- Generate token e copie (`github_pat_...`). Ela vai **só** no cron-job.org.

## 2. cron-job.org (criar conta grátis) — 4 tarefas iguais, muda só o nome, o horário e a tarefa

Jeito mais fácil (usado na instalação): CREATE CRONJOB → **IMPORT FROM CURL** e colar, trocando a chave e a tarefa:

```
curl -X POST https://api.github.com/repos/antonioventuress-cell/moda-estampa-posts/actions/workflows/postagem.yml/dispatches -H "Authorization: Bearer COLE_A_CHAVE_AQUI" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" -d "{\"ref\":\"main\",\"inputs\":{\"tarefa\":\"bom-dia\"}}"
```

Resposta 401 = chave errada/antiga (Regenerate token invalida a anterior). 204 = certo.

Ou à mão, em todas:
- **URL:** `https://api.github.com/repos/antonioventuress-cell/moda-estampa-posts/actions/workflows/postagem.yml/dispatches`
- Aba **Advanced**:
  - **Request method:** `POST`
  - **Headers** (3):
    - `Authorization` = `Bearer ` + a chave (`Bearer github_pat_...`)
    - `Accept` = `application/vnd.github+json`
    - `Content-Type` = `application/json`
  - **Request body:** o da tabela
  - **Time zone:** `America/Sao_Paulo`

| Nome | Quando | Request body |
|---|---|---|
| Bom dia | todo dia, 06:05 | `{"ref":"main","inputs":{"tarefa":"bom-dia"}}` |
| Post do dia | todo dia, 07:30 | `{"ref":"main","inputs":{"tarefa":"sugerir"}}` |
| Promo | terça e quarta, 15:00 | `{"ref":"main","inputs":{"tarefa":"promo"}}` |
| Bot | a cada 1 hora | `{"ref":"main","inputs":{"tarefa":"bot"}}` |

O "Bot" a cada hora mantém o bot sempre ouvindo o Telegram: se já tem um rodando, o novo espera na fila e assume quando o outro acabar.
Teste: em cada tarefa, botão **Test run** → resposta **204** = deu certo.
