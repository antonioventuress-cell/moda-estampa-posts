"""Aplica o padrão da marca numa foto de vestido: 1080x1350 (4:5), logo branco no canto e faixa azul "Chama no direct".
Uso: python padrao_foto.py <foto> [saida.jpg] [--inteira]
--inteira: em vez de cortar, mostra o vestido inteiro sobre fundo creme (fotos do WhatsApp são bem altas).
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parents[2] / "stories"))
from comum import AZUL, BRANCO, CREME, carrega, fonte

W, H, FAIXA = 1080, 1350, 120


def padrao(foto, inteira=False):
    im = Image.open(foto).convert("RGB")
    # print de story vem com as barras pretas do app (nome da loja, "Responder"): fica só o maior trecho claro
    cinza = im.convert("L").resize((1, im.height), Image.BOX)
    ini, melhor = 0, (0, 0)
    for y in range(im.height + 1):
        if y == im.height or cinza.getpixel((0, y)) <= 45:
            if y - ini > melhor[1] - melhor[0]:
                melhor = (ini, y)
            ini = y + 1
    im = im.crop((0, melhor[0], im.width, melhor[1]))
    area = H - FAIXA
    if inteira:
        # fundo: a própria foto desfocada e clareada pra puxar o creme, vestido inteiro por cima
        fundo = im.resize((W, round(im.height * W / im.width))).crop((0, 0, W, area)).filter(ImageFilter.GaussianBlur(40))
        base = Image.blend(fundo, Image.new("RGB", (W, area), CREME), 0.6)
        foto_r = im.resize((round(im.width * area / im.height), area), Image.LANCZOS)
        base.paste(foto_r, ((W - foto_r.width) // 2, 0))
    else:
        esc = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
        topo = round((esc.height - area) * 0.3)  # puxa pra cima: corta mais a barra do vestido que o rosto
        base = esc.crop((0, topo, W, topo + area))
    tela = Image.new("RGB", (W, H), AZUL)
    tela.paste(base, (0, 0))
    logo = carrega("logo-branco.png", 230)
    sombra = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    sombra.putalpha(logo.getchannel("A").point(lambda a: a * 0.45).filter(ImageFilter.GaussianBlur(8)))
    tela.paste(sombra, (W - logo.width - 36, 40), sombra)  # sombra: logo branco some em vestido claro
    tela.paste(logo, (W - logo.width - 40, 36), logo)
    d = ImageDraw.Draw(tela)
    f = fonte("Montserrat.ttf", 46, 800)
    d.text((W // 2, H - FAIXA // 2), "Chama no direct  →", font=f, fill=BRANCO, anchor="mm")
    return tela


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--inteira"]
    saida = Path(args[1]) if len(args) > 1 else Path(args[0]).with_suffix(".post.jpg")
    padrao(args[0], "--inteira" in sys.argv).save(saida, quality=92)
    print(saida)
