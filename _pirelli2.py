"""Continuar Pirelli a partir do Diablo Rosso I (retomada após erro de nome)"""
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
PASTA = r'c:\agente-v5-clone\Pneus\Pirelli'


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


# ── Diablo Rosso I 130/70-13 traseiro ──
upload_e_vincular(
    "Pneu-pirelli-scotter-diablo-130-70-13-traseiro-principal-sem câmera.jpg",
    "pneus/pirelli/diablo-rosso-i/130-70-13/traseiro/principal.webp",
    "acfc9462-a7f3-47c0-8ef6-d1b10271975a", "principal", 1, "Pirelli Diablo Rosso I 130/70-13"
)
upload_e_vincular(
    "Pneu-pirelli-scotter-diablo-130-70-13-traseiro-frontal-sem câmera.jpg",
    "pneus/pirelli/diablo-rosso-i/130-70-13/traseiro/frontal.webp",
    "acfc9462-a7f3-47c0-8ef6-d1b10271975a", "frontal", 2, "Pirelli Diablo Rosso I 130/70-13"
)

# ── Diablo Rosso II 110/70-17 dianteiro ──
upload_e_vincular(
    "Pneu-Pirelli-Diablo-Rosso-2-110-70-17-Dianteiro-principal.jpg",
    "pneus/pirelli/diablo-rosso-ii/110-70-17/dianteiro/principal.webp",
    "708ee9e4-a192-4c48-9efb-37bec53f8405", "principal", 1, "Pirelli Diablo Rosso II 110/70-17"
)
upload_e_vincular(
    "Pneu-Pirelli-Diablo-Rosso-2-110-70-17-Dianteiro-frontal.jpg",
    "pneus/pirelli/diablo-rosso-ii/110-70-17/dianteiro/frontal.webp",
    "708ee9e4-a192-4c48-9efb-37bec53f8405", "frontal", 2, "Pirelli Diablo Rosso II 110/70-17"
)

# ── Diablo Rosso II 120/70-17 dianteiro ──
upload_e_vincular(
    "Pneu-pirelli-diablo rosso-120-70-17-dianteiro-principal-sem câmara",
    "pneus/pirelli/diablo-rosso-ii/120-70-17/dianteiro/principal.webp",
    "228ce52d-94d7-4ae5-816c-d5642276cbc4", "principal", 1, "Pirelli Diablo Rosso II 120/70-17"
)
upload_e_vincular(
    "Pneu-pirelli-diablo rosso-120-70-17-dianteiro-frontal-sem câmara",
    "pneus/pirelli/diablo-rosso-ii/120-70-17/dianteiro/frontal.webp",
    "228ce52d-94d7-4ae5-816c-d5642276cbc4", "frontal", 2, "Pirelli Diablo Rosso II 120/70-17"
)
upload_e_vincular(
    "Pneu-pirelli-diablo rosso-120-70-17-dianteiro-frontal-sem câmara.mov",
    "pneus/pirelli/diablo-rosso-ii/120-70-17/dianteiro/video.mp4",
    "228ce52d-94d7-4ae5-816c-d5642276cbc4", "video", 3, "Pirelli Diablo Rosso II 120/70-17",
    is_video=True
)

# ── Diablo Rosso II 140/70-17 traseiro (só frontal) ──
upload_e_vincular(
    "Pirelli-diablo Rosso-140-70-17-traseiro-frontal-sem câmara",
    "pneus/pirelli/diablo-rosso-ii/140-70-17/traseiro/frontal.webp",
    "06c908f7-020b-4f17-82cf-46fdaa7c2d36", "frontal", 2, "Pirelli Diablo Rosso II 140/70-17"
)

# ── Diablo Rosso III 110/70-17 dianteiro ──
upload_e_vincular(
    "Pneu-pirelli-diablo-rosso 3-110-70-17-dianteiro-principal-sem camera",
    "pneus/pirelli/diablo-rosso-iii/110-70-17/dianteiro/principal.webp",
    "4f59227d-6b7f-4ffd-837d-e330c5d80fdf", "principal", 1, "Pirelli Diablo Rosso III 110/70-17"
)
upload_e_vincular(
    "Pneu-pirelli-diablo-rosso 3-110-70-17-dianteiro-frontal-sem câmera",
    "pneus/pirelli/diablo-rosso-iii/110-70-17/dianteiro/frontal.webp",
    "4f59227d-6b7f-4ffd-837d-e330c5d80fdf", "frontal", 2, "Pirelli Diablo Rosso III 110/70-17"
)

# ── Diablo Scooter ADV 130/70-13 traseiro ──
upload_e_vincular(
    "Pneu-Pirelli diablo scotter -adv-traseiro-principal-sem câmera",
    "pneus/pirelli/diablo-scooter-adv/130-70-13/traseiro/principal.webp",
    "6a843776-66a5-4aca-920f-2181d87d726a", "principal", 1, "Pirelli Diablo Scooter ADV 130/70-13"
)
upload_e_vincular(
    "Pneu-Pirelli diablo scotter -adv-traseiro-frontal-sem câmara",
    "pneus/pirelli/diablo-scooter-adv/130-70-13/traseiro/frontal.webp",
    "6a843776-66a5-4aca-920f-2181d87d726a", "frontal", 2, "Pirelli Diablo Scooter ADV 130/70-13"
)

# ── Phantom 150/70-17 traseiro ──
upload_e_vincular(
    "Pirelli-phantom-150-70-17-traseiro-principa-sem câmara",
    "pneus/pirelli/phantom/150-70-17/traseiro/principal.webp",
    "c60392a8-5706-4057-b292-044105a93953", "principal", 1, "Pirelli Phantom 150/70-17"
)
upload_e_vincular(
    "Pirelli-phantom-150-70-17-traseiro-frontal-se camera",
    "pneus/pirelli/phantom/150-70-17/traseiro/frontal.webp",
    "c60392a8-5706-4057-b292-044105a93953", "frontal", 2, "Pirelli Phantom 150/70-17"
)
upload_e_vincular(
    "Pirelli-phantom-150-70-17-traseiro-frontal-se camera vídeo.mov",
    "pneus/pirelli/phantom/150-70-17/traseiro/video.mp4",
    "c60392a8-5706-4057-b292-044105a93953", "video", 3, "Pirelli Phantom 150/70-17",
    is_video=True
)

# ── Scorpion Trail II 150/70-17 traseiro ──
upload_e_vincular(
    "Pirelli-scorpion-150-70-17-traseiro-princ-se câmera",
    "pneus/pirelli/scorpion-trail-ii/150-70-17/traseiro/principal.webp",
    "2e3d9e86-0328-4eac-8da5-9ccb45f4cebe", "principal", 1, "Pirelli Scorpion Trail II 150/70-17"
)
upload_e_vincular(
    "Pirelli-scorpion-150-70-17-traseiro-frontal-se camera",
    "pneus/pirelli/scorpion-trail-ii/150-70-17/traseiro/frontal.webp",
    "2e3d9e86-0328-4eac-8da5-9ccb45f4cebe", "frontal", 2, "Pirelli Scorpion Trail II 150/70-17"
)
upload_e_vincular(
    "Pirelli-scorpion-150-70-17-traseiro-frontal-se camera vídeo.mov",
    "pneus/pirelli/scorpion-trail-ii/150-70-17/traseiro/video.mp4",
    "2e3d9e86-0328-4eac-8da5-9ccb45f4cebe", "video", 3, "Pirelli Scorpion Trail II 150/70-17",
    is_video=True
)

# ── Sport Demon 100/80-17 dianteiro ──
upload_e_vincular(
    "Pirelli-sport-damon-100-80-17-dianteiro-principal.jpg",
    "pneus/pirelli/sport-demon/100-80-17/dianteiro/principal.webp",
    "5f36df48-8517-496c-b8e4-4b104416be09", "principal", 1, "Pirelli Sport Demon 100/80-17"
)

# ── Sport Demon 110/70-17 dianteiro ──
upload_e_vincular(
    "Pirelli-sport-damon-110-70-17-dianteiro-principal.jpg",
    "pneus/pirelli/sport-demon/110-70-17/dianteiro/principal.webp",
    "ce33e888-0c0f-4cb5-90a5-bd0ac31647b4", "principal", 1, "Pirelli Sport Demon 110/70-17"
)
upload_e_vincular(
    "Pirelli-sport-damon-110-70-17-dianteiro-frontal.jpg",
    "pneus/pirelli/sport-demon/110-70-17/dianteiro/frontal.webp",
    "ce33e888-0c0f-4cb5-90a5-bd0ac31647b4", "frontal", 2, "Pirelli Sport Demon 110/70-17"
)

# ── Sport Demon 140/70-17 traseiro ──
upload_e_vincular(
    "Pirelli-sport-damon-140-70-17-traseiro-frontal(1).jpg",
    "pneus/pirelli/sport-demon/140-70-17/traseiro/principal.webp",
    "dc14ec9a-9091-4331-b53f-a2be1fffa961", "principal", 1, "Pirelli Sport Demon 140/70-17"
)
upload_e_vincular(
    "Pirelli-sport-damon-140-70-17-traseiro-frontal.jpg",
    "pneus/pirelli/sport-demon/140-70-17/traseiro/frontal.webp",
    "dc14ec9a-9091-4331-b53f-a2be1fffa961", "frontal", 2, "Pirelli Sport Demon 140/70-17"
)

# ── Sport Demon 150/70-17 traseiro ──
upload_e_vincular(
    "Pirelli-sport-damon-150-70-17-traseiro-principal-sem câmera",
    "pneus/pirelli/sport-demon/150-70-17/traseiro/principal.webp",
    "777f7d66-7332-42e5-acca-c305c98b9599", "principal", 1, "Pirelli Sport Demon 150/70-17"
)
upload_e_vincular(
    "Pirelli-sport-damon-150-70-17-traseiro-frontal-se camera",
    "pneus/pirelli/sport-demon/150-70-17/traseiro/frontal.webp",
    "777f7d66-7332-42e5-acca-c305c98b9599", "frontal", 2, "Pirelli Sport Demon 150/70-17"
)
upload_e_vincular(
    "Pirelli-sport-damon-150-70-17-traseiro-frontal-se camera.mov",
    "pneus/pirelli/sport-demon/150-70-17/traseiro/video.mp4",
    "777f7d66-7332-42e5-acca-c305c98b9599", "video", 3, "Pirelli Sport Demon 150/70-17",
    is_video=True
)

print(f"\n{'='*55}")
print("Pirelli concluído!")
