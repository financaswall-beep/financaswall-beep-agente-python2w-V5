"""Processar pasta Maggion: WebP + marca d'água + vídeo comprimido"""
import os, io, subprocess, tempfile
from dotenv import load_dotenv
from supabase import create_client
from PIL import Image
from pillow_heif import register_heif_opener
import imageio_ffmpeg

register_heif_opener()
load_dotenv(override=True)
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
BASE_URL = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/fotos"
BUCKET = 'fotos'
LOGO_PATH = r'c:\agente-v5-clone\logo_2w.png'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def marca_dagua(img):
    logo = Image.open(LOGO_PATH).convert('RGBA')
    w = max(80, int(img.width * 0.22))
    h = int(logo.height * w / logo.width)
    logo = logo.resize((w, h), Image.LANCZOS)
    r, g, b, a = logo.split()
    a = a.point(lambda x: int(x * 0.70))
    logo.putalpha(a)
    base = img.convert('RGBA')
    base.paste(logo, (img.width - w - 15, img.height - h - 15), logo)
    return base.convert('RGB')


def processar_imagem(local_path):
    img = Image.open(local_path)
    img = marca_dagua(img)
    buf = io.BytesIO()
    img.save(buf, format='WEBP', quality=82)
    return buf.getvalue()


def processar_video(local_path):
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        tmp_out = tmp.name
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tl:
        tmp_logo = tl.name

    logo = Image.open(LOGO_PATH).convert('RGBA')
    logo = logo.resize((180, 180), Image.LANCZOS)
    logo.save(tmp_logo, 'PNG')

    cmd = [
        FFMPEG, '-y', '-i', local_path, '-i', tmp_logo,
        '-filter_complex',
        '[0:v]scale=1280:-2,format=yuv420p[base];[1:v]scale=180:-1,format=rgba,colorchannelmixer=aa=0.7[wm];[base][wm]overlay=W-w-15:H-h-15[out]',
        '-map', '[out]', '-map', '0:a',
        '-c:v', 'libx264', '-crf', '26', '-preset', 'fast',
        '-c:a', 'aac', '-b:a', '96k', tmp_out
    ]
    r = subprocess.run(cmd, capture_output=True)
    os.unlink(tmp_logo)

    if r.returncode != 0:
        print("  Overlay falhou, comprimindo sem marca d'água...")
        cmd2 = [FFMPEG, '-y', '-i', local_path,
                '-vf', 'scale=1280:-2', '-pix_fmt', 'yuv420p',
                '-c:v', 'libx264', '-crf', '26', '-preset', 'fast',
                '-c:a', 'aac', '-b:a', '96k', tmp_out]
        subprocess.run(cmd2, capture_output=True)

    with open(tmp_out, 'rb') as f:
        data = f.read()
    os.unlink(tmp_out)
    print(f"  Vídeo: {len(data)/1024/1024:.1f} MB")
    return data


def upload_e_vincular(local, storage_path, pneu_id, tipo, ordem, nome_pneu, is_video=False, deletar=[]):
    local_path = f"Pneus\\Maggion\\{local}"
    print(f"\n{'='*55}")
    print(f"Processando: {local}")

    if is_video:
        data = processar_video(local_path)
        mime = 'video/mp4'
    else:
        data = processar_imagem(local_path)
        mime = 'image/webp'
        print(f"  Imagem: {len(data)/1024:.0f} KB")

    print(f"  Upload → {storage_path} ...", end=" ")
    supabase.storage.from_(BUCKET).upload(storage_path, data, {'content-type': mime, 'upsert': 'true'})
    print("OK")

    url = f"{BASE_URL}/{storage_path}"
    supabase.table('foto_pneu').upsert(
        {'pneu_id': pneu_id, 'url': url, 'tipo': tipo, 'ordem': ordem,
         'nome_pneu': nome_pneu, 'ativo': True},
        on_conflict='pneu_id,tipo,ordem').execute()
    print("  foto_pneu: OK")

    for p in deletar:
        try:
            supabase.storage.from_(BUCKET).remove([p])
            print(f"  Deletado antigo: {p}")
        except:
            pass


# ── Maggion Winner 100/80-18 traseiro ──
upload_e_vincular(
    "Pneu-maggion-100-90-18-traseiro-sem câmera-frontal",
    "pneus/maggion/winner/100-80-18/traseiro/frontal.webp",
    "534e3a26-5cb4-4966-a5f2-8b62e428f0d6", "frontal", 2, "Maggion Winner 100/80-18"
)
upload_e_vincular(
    "Pneu-maggion-10080-18-traseiro-sem câmera-principal",
    "pneus/maggion/winner/100-80-18/traseiro/principal.webp",
    "534e3a26-5cb4-4966-a5f2-8b62e428f0d6", "principal", 1, "Maggion Winner 100/80-18"
)

# ── Maggion Predator 80/100-18 dianteiro ──
upload_e_vincular(
    "Pneu-maggion-80-100-18-dianteiro-sem câmera-frontal.jpg",
    "pneus/maggion/predator/80-100-18/dianteiro/frontal.webp",
    "72031ed0-d37e-4d3c-b3b1-3fa9de5282f3", "frontal", 2, "Maggion Predator 80/100-18"
)
upload_e_vincular(
    "Pneu-maggion-80-100-18-dianteiro-sem câmera-principal.jpg",
    "pneus/maggion/predator/80-100-18/dianteiro/principal.webp",
    "72031ed0-d37e-4d3c-b3b1-3fa9de5282f3", "principal", 1, "Maggion Predator 80/100-18"
)
upload_e_vincular(
    "Pneu-maggion-80-100-18-dianteiro-sem câmera-principal vídeo.mov",
    "pneus/maggion/predator/80-100-18/dianteiro/video.mp4",
    "72031ed0-d37e-4d3c-b3b1-3fa9de5282f3", "video", 3, "Maggion Predator 80/100-18",
    is_video=True
)

print(f"\n{'='*55}")
print("Maggion concluído!")
