"""Testa o bot sem contas: Telegram e Instagram simulados, edição de foto/vídeo de verdade (usa as mídias do
WhatsApp da raiz, então só roda no PC). Uso: python automacao/teste_postar.py"""
import os, shutil, sys, tempfile
from pathlib import Path

PROJ = Path(__file__).parents[1]
os.environ.update(TELEGRAM_TOKEN="x", TELEGRAM_CHAT_ID="42", IG_TOKEN="y", GITHUB_REPOSITORY="dono/repo")
sys.path.insert(0, str(PROJ / "automacao"))
import postar

tmp = Path(tempfile.mkdtemp())
postar.FILA, postar.ESTADO = tmp / "fila", tmp / "estado.json"
enviados, publicados, fila_updates = [], [], []
FONTES = {"foto": PROJ / "WhatsApp Image 2026-10-20 at 10.26.23.jpeg", "vid": PROJ / "WhatsApp Video 2026-10-20 at 10.26.31.mp4"}


def tg(metodo, arquivos=None, **d):
    enviados.append((metodo, d))
    if metodo == "answerCallbackQuery":  # como no real: o toque já é velho quando o bot roda
        raise RuntimeError("Telegram answerCallbackQuery: query is too old")
    if metodo == "getUpdates":
        if d.get("offset") is not None:  # pedir a partir de N confirma (some) os anteriores
            fila_updates[:] = [u for u in fila_updates if u["update_id"] >= d["offset"]]
        return fila_updates[:1]
    if metodo == "getFile":
        return {"file_path": d["file_id"]}
    return {}


class Resp:
    def __init__(s, c): s.content = c


postar.tg = tg
postar.requests.get = lambda url, **k: Resp(FONTES[url.rsplit("/", 1)[1]].read_bytes())
postar.publicar = lambda url, tipo, legenda="": publicados.append((url, tipo, legenda))

# 1) foto chega -> fila/10.jpg + prévia com botões
postar.receber({"chat": {"id": 42}, "message_id": 10, "photo": [{"file_id": "foto"}]})
assert (postar.FILA / "10.jpg").exists()
metodo, d = enviados[-1]
assert metodo == "sendPhoto" and postar.HASHTAGS in d["caption"] and "post:10.jpg" in str(d["reply_markup"])
leg0 = d["caption"]
msg = {"message_id": 99, "caption": leg0}
cb = lambda acao, nome: {"id": "c", "from": {"id": 42}, "data": f"{acao}:{nome}", "message": msg}
# 2) outra legenda
postar.responder(cb("leg", "10.jpg"))
assert enviados[-1][0] == "editMessageCaption" and enviados[-1][1]["caption"] != leg0
# 3) postar -> foto no feed, arquivo sai da fila
postar.responder(cb("post", "10.jpg"))
assert publicados[-1] == ("https://dono.github.io/repo/fila/10.jpg", "IMAGE", leg0)
assert not (postar.FILA / "10.jpg").exists()
# 4) tocar de novo não posta duas vezes
postar.responder(cb("post", "10.jpg"))
assert len(publicados) == 1
# 5) estranho não usa o bot
postar.receber({"chat": {"id": 7}, "message_id": 11, "photo": [{"file_id": "foto"}]})
assert "chat id: 7" in enviados[-1][1]["text"] and not (postar.FILA / "11.jpg").exists()
# 6) vídeo com legenda própria; descartar apaga
postar.receber({"chat": {"id": 42}, "message_id": 12, "video": {"file_id": "vid"}, "caption": "Minha legenda"})
assert enviados[-1][0] == "sendVideo" and enviados[-1][1]["caption"].startswith("Minha legenda")
postar.responder(cb("del", "12.mp4"))
assert not (postar.FILA / "12.mp4").exists() and len(publicados) == 1
# 7) stories: bom dia do dia certo, promo na ordem, não repete no mesmo dia; depois do meio-dia pula o bom dia
oito_horas = postar.agora().replace(hour=8)
postar.agora = lambda: oito_horas
postar.stories("bom-dia")
dia = oito_horas.isoweekday()
assert publicados[-1][1] == "STORIES" and f"/stories/bom-dia/{dia}-" in publicados[-1][0]
postar.stories("bom-dia")
assert len(publicados) == 2
postar.stories("promo")
assert [p[0].split("/")[-2] for p in publicados[-2:]] == ["1-gancho", "2-oferta"]
postar.ESTADO.unlink()
postar.agora = lambda: oito_horas.replace(hour=13)
postar.stories("bom-dia")
assert len(publicados) == 4 and "pulei o bom dia" in enviados[-1][1]["text"]
# 8) loop do bot: uma mensagem com erro avisa e não trava a próxima
fila_updates += [{"update_id": 5, "message": {"chat": {"id": 42}, "message_id": 13, "photo": [{"file_id": "nao-existe"}]}},
                 {"update_id": 6, "message": {"chat": {"id": 42}, "message_id": 14, "photo": [{"file_id": "foto"}]}}]
postar.bot()
assert any(m == "sendMessage" and "Deu erro" in d.get("text", "") for m, d in enviados)
assert (postar.FILA / "14.jpg").exists() and not fila_updates
# 9) escuta longa: com a fila vazia, para sozinha quando o tempo acaba (não trava)
import time as _t
t0 = _t.time(); postar.bot(0.3)
assert 0.3 <= _t.time() - t0 < 5
shutil.rmtree(tmp)
print("ok: todos os testes passaram")
