"""Testa o bot sem contas: Telegram, Instagram e KV da Cloudflare simulados, edição de foto/vídeo de verdade
(usa as mídias do WhatsApp da raiz, então só roda no PC). Uso: python automacao/teste_postar.py"""
import json, os, sys
from pathlib import Path

PROJ = Path(__file__).parents[1]
os.environ.update(TELEGRAM_TOKEN="x", TELEGRAM_CHAT_ID="42", IG_TOKEN="y", WORKER_URL="https://porteiro.dev/",
                  CF_ACCOUNT_ID="a", CF_KV_ID="k", CF_TOKEN="c")
sys.path.insert(0, str(PROJ / "automacao"))
import postar

FONTES = {"foto": PROJ / "WhatsApp Image 2026-10-20 at 10.26.23.jpeg", "vid": PROJ / "WhatsApp Video 2026-10-20 at 10.26.31.mp4"}
enviados, publicados, loja = [], [], {}  # loja = KV simulado {chave: (bytes, metadata)}


def tg(metodo, arquivos=None, **d):
    enviados.append((metodo, d))
    return {"file_path": d["file_id"]} if metodo == "getFile" else {}


class Resp:
    def __init__(s, conteudo=b"", meta=None):
        s.content, s.text, s._meta = conteudo, conteudo.decode(errors="ignore"), meta
    def json(s): return {"result": s._meta}


def kv(metodo, caminho, data=None, files=None):
    tipo, chave = caminho.split("/", 1)
    if metodo == "PUT":
        loja[chave] = (files["value"], json.loads(files["metadata"][1])) if files else (data if isinstance(data, bytes) else data.encode(), None)
    elif metodo == "DELETE":
        loja.pop(chave, None)
    elif chave in loja:
        return Resp(loja[chave][0], loja[chave][1])


postar.tg, postar.kv = tg, kv
postar.requests.get = lambda url, **k: Resp(FONTES[url.rsplit("/", 1)[1]].read_bytes())
postar.publicar = lambda chave, tipo, legenda="": publicados.append((chave, tipo, legenda, chave in loja))

# 1) foto chega -> guardada no KV + prévia com botões
postar.telegram({"message": {"chat": {"id": 42}, "message_id": 10, "photo": [{"file_id": "foto"}]}})
metodo, d = enviados[-1]
chave = d["reply_markup"]["inline_keyboard"][0][0]["callback_data"].split(":")[1]
assert metodo == "sendPhoto" and postar.HASHTAGS in d["caption"] and chave in loja and chave.endswith(".jpg")
leg0 = d["caption"]
msg = {"message_id": 99, "caption": leg0}
cb = lambda acao, ch: {"callback_query": {"id": "c", "from": {"id": 42}, "data": f"{acao}:{ch}", "message": msg}}
# 2) outra legenda
postar.telegram(cb("leg", chave))
assert enviados[-1][0] == "editMessageCaption" and enviados[-1][1]["caption"] != leg0
# 3) postar -> feed, e a mídia some do KV depois
postar.telegram(cb("post", chave))
assert publicados[-1] == (chave, "IMAGE", leg0, True) and chave not in loja
# 4) tocar de novo não posta duas vezes
postar.telegram(cb("post", chave))
assert len(publicados) == 1
# 5) estranho não usa o bot
postar.telegram({"message": {"chat": {"id": 7}, "message_id": 11, "photo": [{"file_id": "foto"}]}})
assert "chat id: 7" in enviados[-1][1]["text"] and not loja
# 6) vídeo -> legenda própria; vídeo grande vai em partes; descartar apaga todas
postar.PARTE = 1024 * 1024
postar.telegram({"message": {"chat": {"id": 42}, "message_id": 12, "video": {"file_id": "vid"}, "caption": "Minha legenda"}})
assert enviados[-1][0] == "sendVideo" and enviados[-1][1]["caption"].startswith("Minha legenda")
chave = enviados[-1][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"].split(":")[1]
partes = loja[chave][1]["partes"]
assert partes > 1 and len(loja) == partes and loja[chave][1]["tamanho"] == sum(len(v[0]) for v in loja.values())
postar.telegram(cb("del", chave))
assert not loja and len(publicados) == 1
# 7) stories: bom dia do dia certo, promo na ordem, mídia apagada depois, não repete no mesmo dia
postar.stories("bom-dia")
assert publicados[-1][1] == "STORIES" and publicados[-1][3] and list(loja) == ["estado-bom-dia"]
postar.stories("bom-dia")
assert len(publicados) == 2
postar.stories("promo")
assert len(publicados) == 4 and set(loja) == {"estado-bom-dia", "estado-promo"}
# 8) erro avisa no Telegram
try:
    postar.telegram({"message": {"chat": {"id": 42}, "message_id": 13, "photo": [{"file_id": "nao-existe"}]}})
except Exception:
    pass
assert "Deu erro" in enviados[-1][1]["text"]
print("ok: todos os testes passaram")
