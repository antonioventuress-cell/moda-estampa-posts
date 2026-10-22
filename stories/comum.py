"""Base compartilhada dos stories: cores, fontes, logos, easing e render com narração."""
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont

RAIZ = Path(__file__).parents[1]
MARCA = RAIZ / "identidade-visual/final"
W, H, FPS = 1080, 1920, 30
CREME, BRANCO, MARINHO = (248, 245, 236), (255, 255, 255), (3, 46, 88)
VERMELHO, SOL, AZUL, VERDE = (225, 29, 46), (255, 198, 41), (0, 87, 168), (46, 139, 87)
MULTI = [VERMELHO, AZUL, VERDE]
INICIO_VOZ = 0.4  # segundos de vídeo antes da narração começar


def carrega(nome, larg):
    im = Image.open(MARCA / nome).convert("RGBA")
    if nome == "logo-fundo-amarelo.png":  # tem fundo e margem: recorta
        fundo = Image.new("RGBA", im.size, im.getpixel((0, 0)))
        im = im.crop(ImageChops.difference(im, fundo).convert("L").point(lambda v: 255 * (v > 30)).getbbox())
    return im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)


def fonte(arquivo, tam, *eixos):
    f = ImageFont.truetype(str(RAIZ / "motion" / arquivo), tam)
    f.set_variation_by_axes(list(eixos))
    return f


def clamp(x): return max(0.0, min(1.0, x))
def ease_out(x): return 1 - (1 - x) ** 3
def back_out(x, s=1.9): x -= 1; return 1 + (s + 1) * x**3 + s * x**2
def prog(t, ini, dur): return clamp((t - ini) / dur)


def texto_fade(img, xy, txt, f, cor, p):
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(camada).text(xy, txt, font=f, fill=cor + (round(255 * p),), anchor="mm")
    img.paste(camada, (0, 0), camada)


def colar_fade(img, peca, x, y, p):
    if p <= 0:
        return
    peca = peca.copy()
    peca.putalpha(peca.getchannel("A").point(lambda v: v * p))
    img.paste(peca, (round(x), round(y)), peca)


def limpar_voz(mp3, wav):
    """Encurta pausas da voz de IA (>0,1s viram ~0,13s no total) e corta silêncio do começo/fim."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                    "silenceremove=start_periods=1:start_threshold=-40dB:"
                    "stop_periods=-1:stop_duration=0.1:stop_silence=0.05:stop_threshold=-35dB",
                    str(wav)], check=True)
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout)


def render(pasta, quadro, dur_min=6.0, t_previa=5.0):
    """Gera pasta/story.mp4. Se houver pasta/narracao.mp3, limpa as pausas, encaixa a voz
    em INICIO_VOZ e estica o vídeo para caber a fala + 1s."""
    pasta.mkdir(exist_ok=True)
    narr = pasta / "narracao.mp3"
    with tempfile.TemporaryDirectory() as tmp:
        voz, dur = None, dur_min
        if narr.exists():
            voz = Path(tmp) / "voz.wav"
            dur = max(dur_min, INICIO_VOZ + limpar_voz(narr, voz) + 1.0)
        entrada_audio = ["-i", str(voz)] if voz else []
        mix = (["-af", f"adelay={int(INICIO_VOZ * 1000)}:all=1,apad", "-c:a", "aac", "-b:a", "160k", "-shortest"]
               if voz else [])
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "-", *entrada_audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
             *mix, "-movflags", "+faststart", str(pasta / "story.mp4")],
            stdin=subprocess.PIPE)
        for n in range(int(dur * FPS)):
            ff.stdin.write(quadro(n / FPS).tobytes())
        ff.stdin.close()
        ff.wait()
    quadro(t_previa).save(pasta / "previa.jpg", quality=88)
