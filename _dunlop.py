"""Processar pasta Dunlop: WebP + marca d'água + vídeo comprimido"""
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
PASTA = r'c:\agente-v5-clone\Pneus\Dunlop'


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


def upload_e_vincular(filename, storage_path, pneu_id, tipo, ordem, nome_pneu, is_video=False):
    local_path = os.path.join(PASTA, filename)
    print(f"\n{'='*55}")
    print(f"Processando: {filename}")

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


# ── Dunlop Generico 140/70-14 traseiro ──
upload_e_vincular(
    "Pneu-dunlop--140-70-14-traseiro-principal-sem câmera",
    "pneus/dunlop/generico/140-70-14/traseiro/principal.webp",
    "0965bce4-7ace-4bdf-8bd1-2cce2f1fb294", "principal", 1, "Dunlop Generico 140/70-14"
)
upload_e_vincular(
    "Pneu-dunlop--140-70-14-traseiro-frontal-sem câmera",
    "pneus/dunlop/generico/140-70-14/traseiro/frontal.webp",
    "0965bce4-7ace-4bdf-8bd1-2cce2f1fb294", "frontal", 2, "Dunlop Generico 140/70-14"
)
upload_e_vincular(
    "Pneu-dunlop--140-70-14-traseiro-princioal-swm câmera.mov",
    "pneus/dunlop/generico/140-70-14/traseiro/video.mp4",
    "0965bce4-7ace-4bdf-8bd1-2cce2f1fb294", "video", 3, "Dunlop Generico 140/70-14",
    is_video=True
)

# ── Dunlop RoadSport 2 180/55-17 traseiro ──
upload_e_vincular(
    "Pneu-dunlop-roadsport-180-55-17-traseiro-princioal-swm câmera",
    "pneus/dunlop/roadsport-2/180-55-17/traseiro/principal.webp",
    "df9ad76d-9b73-401d-aec0-62df90fc8499", "principal", 1, "Dunlop RoadSport 2 180/55-17"
)
upload_e_vincular(
    "Pneu-dunlop-roadsport-180-55-17-traseiro-frontal-swm câmera",
    "pneus/dunlop/roadsport-2/180-55-17/traseiro/frontal.webp",
    "df9ad76d-9b73-401d-aec0-62df90fc8499", "frontal", 2, "Dunlop RoadSport 2 180/55-17"
)
upload_e_vincular(
    "Pneu-dunlop-roadsport-180-55-17-traseiro-princioal-swm câmera vídeo.mov",
    "pneus/dunlop/roadsport-2/180-55-17/traseiro/video.mp4",
    "df9ad76d-9b73-401d-aec0-62df90fc8499", "video", 3, "Dunlop RoadSport 2 180/55-17",
    is_video=True
)

print(f"\n{'='*55}")
print("Dunlop concluído!")
