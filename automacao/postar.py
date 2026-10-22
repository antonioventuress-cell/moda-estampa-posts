"""Postagem automática da Moda Estampa Digital (roda no GitHub Actions, de graça, com o PC desligado).

python automacao/postar.py bot      -> lê o Telegram: foto/vídeo que você mandou vira prévia editada com botões;
                                       ✅ posta no Instagram (foto no feed, vídeo como Reels), 🔄 troca a legenda, ❌ descarta
python automacao/postar.py bom-dia  -> posta o story de bom dia do dia da semana
python automacao/postar.py promo    -> posta os 2 stories da promo das 5 primeiras (terça e quarta)

O arquivo editado espera em fila/ até você aprovar; o Instagram baixa ele pelo GitHub Pages do repositório.
Segredos (Settings > Secrets do repositório): TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, IG_TOKEN.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).parents[1]
FILA, ESTADO = RAIZ / "fila", RAIZ / "automacao/estado.json"
TOKEN, CHAT = os.environ["TELEGRAM_TOKEN"], os.environ.get("TELEGRAM_CHAT_ID", "")
IG = "https://graph.instagram.com/v23.0"
DONO, REPO = os.environ["GITHUB_REPOSITORY"].split("/")
PAGES = f"https://{DONO}.github.io/{REPO}/"

# mesmas regras de instagram/legendas-propostas.md: nada inventado, CTA pro direct, 5 hashtags fixas
HASHTAGS = "#estampadigital #modaestampadigital #vestidolongo #modafeminina #estampatropical"
LEGENDAS = [
    "Tem estampa que a gente olha e já se apaixona 😍 Esse é daqueles! Chama no direct e garante o seu.",
    "Leveza que acompanha cada passo ✨ Vestido longo com estampa que chama atenção sem esforço. Quer ver mais? Chama no direct.",
    "Chegou novidade na vitrine! ✨ Estampa digital com cores que não passam despercebidas. Chama no direct e vem ver.",
    "Quando a estampa faz todo o trabalho, o look está pronto 🎨 Chama no direct e escolhe a sua.",
    "Um look que fala por si 👗 Estampa digital e caimento leve. Chama no direct e conhece o modelo.",
    "Estampa digital: cada detalhe com cor de verdade 🌿 Chama no direct e vem ver de pertinho.",
    "A estampa é a estrela do look ⭐ Vestido longo para quem ama cor. Chama no direct e escolhe o seu.",
    "Estampa digital que faz toda a diferença 🎨 Vestido longo cheio de personalidade. Chama no direct!",
    "Vestido longo, estampa digital e muito estilo ✨ Chama no direct e escolhe o seu.",
    "Cada estampa conta uma história 🌺 Vem conhecer as nossas. Chama no direct!",
]


def tg(metodo, arquivos=None, **dados):
    dados = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in dados.items()}
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{metodo}", data=dados, files=arquivos, timeout=120).json()
    if not r["ok"]:
        raise RuntimeError(f"Telegram {metodo}: {r.get('description')}")
    return r["result"]


def avisar(texto):
    tg("sendMessage", chat_id=CHAT, text=texto)


def ig(caminho, metodo="GET", **dados):
    r = requests.request(metodo, f"{IG}/{caminho}", params={**dados, "access_token": os.environ["IG_TOKEN"]},
                         timeout=60).json()
    if "error" in r:
        raise RuntimeError(f"Instagram: {r['error'].get('message')}")
    return r


def publicar(url, tipo, legenda=""):
    """tipo: IMAGE (feed), REELS ou STORIES. Espera o Instagram baixar e processar, depois publica."""
    for _ in range(30):  # o Pages leva ~1 min pra publicar um arquivo novo
        if requests.head(url, timeout=30).status_code == 200:
            break
        time.sleep(10)
    else:
        raise RuntimeError(f"o arquivo não apareceu no GitHub Pages: {url}")
    eu = ig("me", fields="user_id")["user_id"]
    dados = {"image_url" if url.endswith(".jpg") else "video_url": url}
    if tipo != "IMAGE":
        dados["media_type"] = tipo
    if legenda:
        dados["caption"] = legenda
    container = ig(f"{eu}/media", "POST", **dados)["id"]
    for _ in range(60):
        status = ig(container, fields="status_code")["status_code"]
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("o Instagram não conseguiu processar a mídia")
        time.sleep(5)
    return ig(f"{eu}/media_publish", "POST", creation_id=container)["id"]


def botoes(nome):
    return {"inline_keyboard": [[{"text": "✅ Postar", "callback_data": f"post:{nome}"},
                                 {"text": "🔄 Outra legenda", "callback_data": f"leg:{nome}"},
                                 {"text": "❌ Descartar", "callback_data": f"del:{nome}"}]]}


def receber(msg):
    if str(msg["chat"]["id"]) != CHAT:
        tg("sendMessage", chat_id=msg["chat"]["id"], text=f"Bot privado. Seu chat id: {msg['chat']['id']}")
        return
    doc = msg.get("document") or {}
    if msg.get("photo"):
        fid, ext = msg["photo"][-1]["file_id"], ".jpg"
    elif msg.get("video") or doc.get("mime_type", "").startswith("video/"):
        fid, ext = (msg.get("video") or doc)["file_id"], ".mp4"
    elif doc.get("mime_type", "").startswith("image/"):
        fid, ext = doc["file_id"], ".jpg"
    else:
        avisar("Me manda uma foto ou um vídeo de vestido que eu edito e te mostro antes de postar.")
        return
    nome = f"{msg['message_id']}{ext}"
    FILA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        bruto = Path(tmp) / f"bruto{ext}"
        caminho = tg("getFile", file_id=fid)["file_path"]
        bruto.write_bytes(requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{caminho}", timeout=120).content)
        if ext == ".mp4" and not shutil.which("ffmpeg"):
            subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg", shell=True, check=True)
        script = "instagram/fotos/padrao_foto.py" if ext == ".jpg" else "motion/vestidos_com_encerramento.py"
        subprocess.run([sys.executable, str(RAIZ / script), str(bruto), str(FILA / nome)], check=True)
    legenda = msg.get("caption") or LEGENDAS[msg["message_id"] % len(LEGENDAS)]
    if HASHTAGS not in legenda:
        legenda += "\n\n" + HASHTAGS
    metodo, campo = ("sendPhoto", "photo") if ext == ".jpg" else ("sendVideo", "video")
    with open(FILA / nome, "rb") as f:
        tg(metodo, {campo: f}, chat_id=CHAT, caption=legenda, reply_markup=botoes(nome))


def responder(cb):
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    if str(cb["from"]["id"]) != CHAT:
        return
    acao, nome = cb["data"].split(":")
    m, arq = cb["message"], FILA / nome
    if not arq.exists():
        avisar("Esse já foi postado ou descartado.")
        return
    sem_botoes = dict(chat_id=CHAT, message_id=m["message_id"], reply_markup={"inline_keyboard": []})
    if acao == "leg":
        atual = m.get("caption", "").split("\n\n")[0]
        i = (LEGENDAS.index(atual) + 1) % len(LEGENDAS) if atual in LEGENDAS else 0
        tg("editMessageCaption", chat_id=CHAT, message_id=m["message_id"],
           caption=f"{LEGENDAS[i]}\n\n{HASHTAGS}", reply_markup=botoes(nome))
    elif acao == "del":
        arq.unlink()
        tg("editMessageReplyMarkup", **sem_botoes)
        avisar("Descartado ❌")
    else:
        tg("editMessageReplyMarkup", **sem_botoes)  # tira os botões antes: evita postar duas vezes
        try:
            publicar(PAGES + "fila/" + nome, "IMAGE" if nome.endswith(".jpg") else "REELS", m.get("caption", ""))
        except Exception:
            tg("editMessageReplyMarkup", chat_id=CHAT, message_id=m["message_id"], reply_markup=botoes(nome))
            raise
        arq.unlink()
        avisar("Postado no Instagram ✅")


def bot():
    prox = None
    while ups := tg("getUpdates", offset=prox, limit=1, timeout=0):  # um por vez: pedir o próximo confirma o anterior
        u = ups[0]
        prox = u["update_id"] + 1
        try:
            if "message" in u:
                receber(u["message"])
            elif "callback_query" in u:
                responder(u["callback_query"])
        except Exception as e:  # avisa e segue: um erro não pode travar a fila
            avisar(f"❌ Deu erro: {e}")
    if prox:
        tg("getUpdates", offset=prox, limit=1, timeout=0)  # confirma o último


def stories(tipo):
    hoje = datetime.now(timezone(timedelta(hours=-3)))  # Brasília; sem horário de verão desde 2019
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    if estado.get(tipo) == f"{hoje:%Y-%m-%d}":
        return  # já postou hoje (ex.: rodou duas vezes)
    pasta = f"stories/bom-dia/{hoje.isoweekday()}-*" if tipo == "bom-dia" else "stories/promo-5-primeiras/*"
    arquivos = sorted(RAIZ.glob(f"{pasta}/story.mp4"))  # promo: 1-gancho antes de 2-oferta
    if not arquivos:
        raise RuntimeError(f"nenhum story em {pasta}")
    for arq in arquivos:
        publicar(PAGES + arq.relative_to(RAIZ).as_posix(), "STORIES")
    estado[tipo] = f"{hoje:%Y-%m-%d}"  # o commit diário disso também mantém o agendamento do GitHub ativo
    ESTADO.write_text(json.dumps(estado, indent=1))
    avisar(f"Story {'de bom dia' if tipo == 'bom-dia' else 'da promo'} postado ✅")


if __name__ == "__main__":
    tarefa = sys.argv[1] if len(sys.argv) > 1 else "bot"
    if tarefa == "bot":
        bot()
    else:
        try:
            stories(tarefa)
        except Exception as e:
            avisar(f"❌ Story {tarefa} não foi postado: {e}")
            raise
