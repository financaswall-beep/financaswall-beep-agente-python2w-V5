"""Processar pasta Michellin: WebP + marca d'água + vídeo comprimido"""
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
PASTA = r'c:\agente-v5-clone\Pneus\Michellin'


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


# ── Michelin City 100/90-18 traseiro ──
upload_e_vincular(
    "Pneu-michellin-100-90-18-city-extra-traseiro-sem-câmara-principal.jpg",
    "pneus/michelin/city/100-90-18/traseiro/principal.webp",
    "f80a145b-08c4-458c-b55b-1503d09b3e7e", "principal", 1, "Michelin City 100/90-18"
)
upload_e_vincular(
    "Pneu-michellin-100-90-18-city-extra-traseiro-sem-câmara-frontal.jpg",
    "pneus/michelin/city/100-90-18/traseiro/frontal.webp",
    "f80a145b-08c4-458c-b55b-1503d09b3e7e", "frontal", 2, "Michelin City 100/90-18"
)

# ── Michelin City Grip 130/70-13 traseiro ──
upload_e_vincular(
    "Pneu-michellin-130-17-13-traseiro-principal-sem câmara.jpg",
    "pneus/michelin/city-grip/130-70-13/traseiro/principal.webp",
    "8031eae0-686d-4a4e-9185-1f0d4d631917", "principal", 1, "Michelin City Grip 130/70-13"
)
upload_e_vincular(
    "Pneu-michellin-130-17-13-traseiro-frontal-sem câmara.jpg",
    "pneus/michelin/city-grip/130-70-13/traseiro/frontal.webp",
    "8031eae0-686d-4a4e-9185-1f0d4d631917", "frontal", 2, "Michelin City Grip 130/70-13"
)

# ── Michelin Pilot 80/100-18 dianteiro ──
upload_e_vincular(
    "Pneu-michellin-80-100-18-pillot-street-diateiro-sem-câmara-principal.jpg",
    "pneus/michelin/pilot/80-100-18/dianteiro/principal.webp",
    "71fa0758-3866-44b2-a45c-44ac685ff9ae", "principal", 1, "Michelin Pilot 80/100-18"
)
upload_e_vincular(
    "Pneu-michellin-80-100-18-pillot-street-diateiro-sem-câmara-frontal.jpg",
    "pneus/michelin/pilot/80-100-18/dianteiro/frontal.webp",
    "71fa0758-3866-44b2-a45c-44ac685ff9ae", "frontal", 2, "Michelin Pilot 80/100-18"
)

# ── Michelin Anakee 3 150/70-17 traseiro ──
upload_e_vincular(
    "Pneu-michellin-analkee 3-150-70-17-traseiro-principal -sem câmera",
    "pneus/michelin/anakee-3/150-70-17/traseiro/principal.webp",
    "00973d00-6073-4208-89e0-b62ce4cd6a9f", "principal", 1, "Michelin Anakee 3 150/70-17"
)
upload_e_vincular(
    "Pneu-michellin-anakee3-150-70-17-traseiro-frontal-sem câmera",
    "pneus/michelin/anakee-3/150-70-17/traseiro/frontal.webp",
    "00973d00-6073-4208-89e0-b62ce4cd6a9f", "frontal", 2, "Michelin Anakee 3 150/70-17"
)
upload_e_vincular(
    "Pneu-michellin-anakee adventure-150-70-17-traseiro-frontal-sem câmera vídeo.mov",
    "pneus/michelin/anakee-3/150-70-17/traseiro/video.mp4",
    "00973d00-6073-4208-89e0-b62ce4cd6a9f", "video", 3, "Michelin Anakee 3 150/70-17",
    is_video=True
)

# ── Michelin Anakee Adventure 170/60-17 traseiro ──
upload_e_vincular(
    "Pneu-michellin-anakee adventure-170-60-17-traseiro-principal-sem câmera",
    "pneus/michelin/anakee-adventure/170-60-17/traseiro/principal.webp",
    "65940607-d473-4abe-8e3a-afaef623800a", "principal", 1, "Michelin Anakee Adventure 170/60-17"
)
upload_e_vincular(
    "Pneu-michellin-anakee adventure-170-60-17-traseiro-frontal-sem câmera",
    "pneus/michelin/anakee-adventure/170-60-17/traseiro/frontal.webp",
    "65940607-d473-4abe-8e3a-afaef623800a", "frontal", 2, "Michelin Anakee Adventure 170/60-17"
)
upload_e_vincular(
    "Pneu-michellin-anakee adventure-170-60-17-traseiro-principal-sem câmera vídeo.mov",
    "pneus/michelin/anakee-adventure/170-60-17/traseiro/video.mp4",
    "65940607-d473-4abe-8e3a-afaef623800a", "video", 3, "Michelin Anakee Adventure 170/60-17",
    is_video=True
)

# ── Michelin Road 5 120/70-17 dianteiro (Angel GT) ──
upload_e_vincular(
    "Pneu-michellin-angel-120-70-17-dianteiro-sem câmera-principal",
    "pneus/michelin/road-5/120-70-17/dianteiro/principal.webp",
    "02d6182b-1cc3-4e63-acec-61aa0eb9f07d", "principal", 1, "Michelin Road 5 120/70-17"
)
upload_e_vincular(
    "Pneu-michellin-angel-120-70-17-dianteiro-frontal-sem camera",
    "pneus/michelin/road-5/120-70-17/dianteiro/frontal.webp",
    "02d6182b-1cc3-4e63-acec-61aa0eb9f07d", "frontal", 2, "Michelin Road 5 120/70-17"
)
upload_e_vincular(
    "Pneu-michellin-angel-120-70-17-dianteiro-sem câmera-vídeo.mov",
    "pneus/michelin/road-5/120-70-17/dianteiro/video.mp4",
    "02d6182b-1cc3-4e63-acec-61aa0eb9f07d", "video", 3, "Michelin Road 5 120/70-17",
    is_video=True
)

print(f"\n{'='*55}")
print("Michelin concluído!")
