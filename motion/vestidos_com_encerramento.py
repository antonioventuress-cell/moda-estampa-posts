"""Junta o encerramento (motion/encerramento.mp4) no fim de cada vídeo de vestido da raiz do projeto.
Uso: python vestidos_com_encerramento.py        (ou com números: ... 1 5 = só vestido-01 e 05)
Saída: instagram/videos-vestidos/vestido-NN.mp4 (1080x1920, 30fps), na ordem do nome do arquivo original.
Um vídeo só (é assim que o fluxo de postagem chama): python vestidos_com_encerramento.py video.mp4 [saida.mp4]
Se existir motion/narracao-encerramento.mp3 (voz Amanda Kelly), ela entra no encerramento; o
encerramento estica (congela o último quadro) se a fala for longa.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "stories"))
from comum import limpar_voz

SAIDA = RAIZ / "instagram/videos-vestidos"
ENCERRAMENTO, NARRACAO = AQUI / "encerramento.mp4", AQUI / "narracao-encerramento.mp3"
DUR_ENC = 4.0
# Voz limpa: "Gostou?" 0-0,5s, "Peça o seu!" 0,6-1,3s, "Chama no direct!" 1,5-2,5s.
# Entrando em 1,3s, o "Chama no direct" cai no toque do botão (2,8s do encerramento).
INICIO_VOZ = 1.3
AUDIO = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"


def duracao_video(arq):
    return float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=duration", "-of", "csv=p=0", str(arq)],
                                capture_output=True, text=True).stdout)


def com_encerramento(video, destino, voz, dur):
    entrada_voz = ["-i", str(voz)] if voz else ["-f", "lavfi", "-i", "anullsrc"]
    atraso = f"adelay={int(INICIO_VOZ * 1000)}:all=1,volume=2," if voz else ""  # +6dB: voz ficava baixa
    dv = duracao_video(video)
    # áudio cortado/completado na duração exata da imagem (alguns têm até 0,3s a mais e
    # atrasavam a voz do encerramento) + fade curto antes do encerramento
    filtro = (f"[0:v]scale=1080:1920,setsar=1,fps=30[v0];"
              f"[0:a]apad,atrim=0:{dv:.3f},afade=t=out:st={dv - 0.4:.3f}:d=0.4,{AUDIO}[a0];"
              f"[1:v]tpad=stop_mode=clone:stop_duration={dur - DUR_ENC:.2f},setsar=1[v1];"
              f"[2:a]{atraso}apad,atrim=0:{dur:.2f},{AUDIO}[a1];"
              "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(ENCERRAMENTO),
                    *entrada_voz, "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
                    "-threads", "2", "-filter_complex_threads", "1",  # leve: o PC travava com todos os núcleos
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(destino)], check=True)
    print(destino, "<-", Path(video).name)


with tempfile.TemporaryDirectory() as tmp:
    voz, dur = None, DUR_ENC
    if NARRACAO.exists():
        voz = Path(tmp) / "voz.wav"
        dur = max(DUR_ENC, INICIO_VOZ + limpar_voz(NARRACAO, voz) + 0.8)
    if sys.argv[1:] and sys.argv[1].lower().endswith(".mp4"):  # um vídeo só
        entrada = Path(sys.argv[1])
        com_encerramento(entrada, Path(sys.argv[2]) if len(sys.argv) > 2 else entrada.with_suffix(".post.mp4"), voz, dur)
    else:
        SAIDA.mkdir(parents=True, exist_ok=True)
        so = {int(a) for a in sys.argv[1:]}  # ex.: python vestidos_com_encerramento.py 1 5 -> só esses
        for n, video in enumerate(sorted(RAIZ.glob("WhatsApp Video *.mp4")), 1):
            if not so or n in so:
                com_encerramento(video, SAIDA / f"vestido-{n:02d}.mp4", voz, dur)
