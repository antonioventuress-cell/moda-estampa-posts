"""Postagem automática da Moda Estampa Digital (GitHub Actions privado + porteiro na Cloudflare, tudo grátis,
com o PC desligado).

python automacao/postar.py telegram -> o porteiro acordou o Actions com uma mensagem do Telegram: foto/vídeo vira
                                       prévia editada com botões; ✅ posta (foto no feed, vídeo como Reels),
                                       🔄 troca a legenda, ❌ descarta
python automacao/postar.py bom-dia  -> posta o story de bom dia do dia da semana
python automacao/postar.py promo    -> posta os 2 stories da promo das 5 primeiras (terça e quarta)
python automacao/postar.py webhook  -> liga o Telegram ao porteiro (uma vez só, na instalação)

O Instagram só baixa mídia de link público: o arquivo fica no KV da Cloudflare e o porteiro entrega por um link
secreto (<WORKER_URL>/m/<chave aleatória>), apagado depois de postar.
Segredos: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, IG_TOKEN, TG_SEGREDO, CF_TOKEN. Variáveis: WORKER_URL, CF_ACCOUNT_ID, CF_KV_ID.
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).parents[1]
TOKEN, CHAT = os.environ["TELEGRAM_TOKEN"], os.environ.get("TELEGRAM_CHAT_ID", "")
IG = "https://graph.instagram.com/v23.0"
WORKER = os.environ["WORKER_URL"].rstrip("/")
KV = (f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CF_ACCOUNT_ID']}"
      f"/storage/kv/namespaces/{os.environ['CF_KV_ID']}/")
PARTE = 20 * 1024 * 1024  # o KV aceita no máximo 25 MB por valor; vídeo maior vai em partes

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


def kv(metodo, caminho, **kw):
    r = requests.request(metodo, KV + caminho, headers={"Authorization": f"Bearer {os.environ['CF_TOKEN']}"},
                         timeout=120, **kw)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r


def guardar(arquivo):
    """Sobe a mídia pro KV e devolve a chave (aleatória: é ela que deixa o link secreto)."""
    chave = secrets.token_hex(8) + Path(arquivo).suffix
    dados = Path(arquivo).read_bytes()
    partes = [dados[i:i + PARTE] for i in range(0, len(dados), PARTE)]
    for i, p in enumerate(partes[1:], 1):
        kv("PUT", f"values/{chave}.{i}", data=p)
    kv("PUT", f"values/{chave}", files={"value": partes[0],
                                       "metadata": (None, json.dumps({"partes": len(partes), "tamanho": len(dados)}))})
    return chave


def existe(chave):
    return kv("GET", f"metadata/{chave}") is not None


def apagar(chave):
    meta = kv("GET", f"metadata/{chave}")
    partes = (meta.json().get("result") or {}).get("partes", 1) if meta else 1
    for i in range(1, partes):
        kv("DELETE", f"values/{chave}.{i}")
    kv("DELETE", f"values/{chave}")


def ig(caminho, metodo="GET", **dados):
    r = requests.request(metodo, f"{IG}/{caminho}", params={**dados, "access_token": os.environ["IG_TOKEN"]},
                         timeout=60).json()
    if "error" in r:
        raise RuntimeError(f"Instagram: {r['error'].get('message')}")
    return r


def publicar(chave, tipo, legenda=""):
    """tipo: IMAGE (feed), REELS ou STORIES. Espera o Instagram baixar e processar, depois publica."""
    url = f"{WORKER}/m/{chave}"
    for _ in range(12):  # o KV leva até 1 min pra espalhar um valor novo pelo mundo
        if requests.head(url, timeout=30).status_code == 200:
            break
        time.sleep(10)
    else:
        raise RuntimeError(f"o porteiro não achou a mídia {chave}")
    eu = ig("me", fields="user_id")["user_id"]
    dados = {"image_url" if chave.endswith(".jpg") else "video_url": url}
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


def botoes(chave):
    return {"inline_keyboard": [[{"text": "✅ Postar", "callback_data": f"post:{chave}"},
                                 {"text": "🔄 Outra legenda", "callback_data": f"leg:{chave}"},
                                 {"text": "❌ Descartar", "callback_data": f"del:{chave}"}]]}


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
    with tempfile.TemporaryDirectory() as tmp:
        bruto, pronto = Path(tmp) / f"bruto{ext}", Path(tmp) / f"pronto{ext}"
        caminho = tg("getFile", file_id=fid)["file_path"]
        bruto.write_bytes(requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{caminho}", timeout=120).content)
        if ext == ".mp4" and not shutil.which("ffmpeg"):
            subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg", shell=True, check=True)
        script = "instagram/fotos/padrao_foto.py" if ext == ".jpg" else "motion/vestidos_com_encerramento.py"
        subprocess.run([sys.executable, str(RAIZ / script), str(bruto), str(pronto)], check=True)
        chave = guardar(pronto)
        legenda = msg.get("caption") or LEGENDAS[msg["message_id"] % len(LEGENDAS)]
        if HASHTAGS not in legenda:
            legenda += "\n\n" + HASHTAGS
        metodo, campo = ("sendPhoto", "photo") if ext == ".jpg" else ("sendVideo", "video")
        with open(pronto, "rb") as f:
            tg(metodo, {campo: f}, chat_id=CHAT, caption=legenda, reply_markup=botoes(chave))


def responder(cb):
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    if str(cb["from"]["id"]) != CHAT:
        return
    acao, chave = cb["data"].split(":")
    m = cb["message"]
    if not existe(chave):
        avisar("Esse já foi postado ou descartado.")
        return
    sem_botoes = dict(chat_id=CHAT, message_id=m["message_id"], reply_markup={"inline_keyboard": []})
    if acao == "leg":
        atual = m.get("caption", "").split("\n\n")[0]
        i = (LEGENDAS.index(atual) + 1) % len(LEGENDAS) if atual in LEGENDAS else 0
        tg("editMessageCaption", chat_id=CHAT, message_id=m["message_id"],
           caption=f"{LEGENDAS[i]}\n\n{HASHTAGS}", reply_markup=botoes(chave))
    elif acao == "del":
        apagar(chave)
        tg("editMessageReplyMarkup", **sem_botoes)
        avisar("Descartado ❌")
    else:
        tg("editMessageReplyMarkup", **sem_botoes)  # tira os botões antes: evita postar duas vezes
        try:
            publicar(chave, "IMAGE" if chave.endswith(".jpg") else "REELS", m.get("caption", ""))
        except Exception:
            tg("editMessageReplyMarkup", chat_id=CHAT, message_id=m["message_id"], reply_markup=botoes(chave))
            raise
        apagar(chave)
        avisar("Postado no Instagram ✅")


def telegram(update):
    try:
        if "message" in update:
            receber(update["message"])
        elif "callback_query" in update:
            responder(update["callback_query"])
    except Exception as e:
        avisar(f"❌ Deu erro: {e}")
        raise


def stories(tipo):
    hoje = f"{datetime.now(timezone(timedelta(hours=-3))):%Y-%m-%d}"  # Brasília; sem horário de verão desde 2019
    feito = kv("GET", f"values/estado-{tipo}")
    if feito is not None and feito.text == hoje:
        return  # já postou hoje (ex.: rodou duas vezes)
    dia = datetime.now(timezone(timedelta(hours=-3))).isoweekday()
    pasta = f"stories/bom-dia/{dia}-*" if tipo == "bom-dia" else "stories/promo-5-primeiras/*"
    arquivos = sorted(RAIZ.glob(f"{pasta}/story.mp4"))  # promo: 1-gancho antes de 2-oferta
    if not arquivos:
        raise RuntimeError(f"nenhum story em {pasta}")
    for arq in arquivos:
        chave = guardar(arq)
        try:
            publicar(chave, "STORIES")
        finally:
            apagar(chave)
    kv("PUT", f"values/estado-{tipo}", data=hoje)
    avisar(f"Story {'de bom dia' if tipo == 'bom-dia' else 'da promo'} postado ✅")


if __name__ == "__main__":
    tarefa = sys.argv[1]
    if tarefa == "telegram":
        telegram(json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["client_payload"]["update"])
    elif tarefa == "webhook":
        tg("setWebhook", url=f"{WORKER}/telegram", secret_token=os.environ["TG_SEGREDO"],
           allowed_updates=["message", "callback_query"])
        print("Telegram ligado ao porteiro")
    else:
        try:
            stories(tarefa)
        except Exception as e:
            avisar(f"❌ Story {tarefa} não foi postado: {e}")
            raise
