"""Processa os 2 pendentes: principal Interact + video Tourance"""
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

# 1. Principal Interact 140/70-17
print("=== Interact principal ===")
img = Image.open(r'Pneus\Meltzeller\Pneu-Metzeller-140-70-17-trasero-principal-sem câmera.jpg')
img = marca_dagua(img)
buf = io.BytesIO()
img.save(buf, format='WEBP', quality=82)
data = buf.getvalue()
supabase.storage.from_(BUCKET).upload(
    'pneus/metzeler/interact/140-70-17/traseiro/principal.webp',
    data, {'content-type': 'image/webp', 'upsert': 'true'})
supabase.table('foto_pneu').upsert(
    {'pneu_id': '4f5e59f6-34da-41af-b47e-e8cb5d37e7f6',
     'url': BASE_URL + '/pneus/metzeler/interact/140-70-17/traseiro/principal.webp',
     'tipo': 'principal', 'ordem': 1,
     'nome_pneu': 'Metzeler Interact 140/70-17', 'ativo': True},
    on_conflict='pneu_id,tipo,ordem').execute()
supabase.storage.from_(BUCKET).remove(['pneus/metzeler/interact/140-70-17/traseiro/principal.jpg'])
print("OK")

# 2. Video Tourance 110/80-14
print("=== Tourance video ===")
local_v = r'Pneus\Meltzeller\Pneu-metzeller-tourance-110-80-14-dianteiro-sem câmera-vídeo.mov'

with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
    tmp_out = tmp.name
with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tl:
    tmp_logo = tl.name

logo = Image.open(LOGO_PATH).convert('RGBA')
logo = logo.resize((160, 160), Image.LANCZOS)
logo.save(tmp_logo, 'PNG')

cmd = [
    FFMPEG, '-y', '-i', local_v, '-i', tmp_logo,
    '-filter_complex',
    '[0:v]scale=1280:-2,transpose=1,format=yuv420p[base];[1:v]scale=180:-1,format=rgba,colorchannelmixer=aa=0.7[wm];[base][wm]overlay=W-w-15:H-h-15[out]',
    '-map', '[out]', '-map', '0:a',
    '-c:v', 'libx264', '-crf', '26', '-preset', 'fast',
    '-c:a', 'aac', '-b:a', '96k', tmp_out
]
r = subprocess.run(cmd, capture_output=True)
os.unlink(tmp_logo)

if r.returncode != 0:
    print("Overlay falhou, comprimindo sem marca d'agua...")
    print(r.stderr.decode()[-300:])
    cmd2 = [FFMPEG, '-y', '-i', local_v,
            '-vf', 'scale=1280:-2,transpose=1',
            '-pix_fmt', 'yuv420p',
            '-c:v', 'libx264', '-crf', '26', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '96k', tmp_out]
    subprocess.run(cmd2)

with open(tmp_out, 'rb') as f:
    vdata = f.read()
os.unlink(tmp_out)
print(f"Tamanho: {len(vdata)/1024/1024:.1f} MB")

supabase.storage.from_(BUCKET).upload(
    'pneus/metzeler/tourance/110-80-14/dianteiro/video.mp4',
    vdata, {'content-type': 'video/mp4', 'upsert': 'true'})
supabase.table('foto_pneu').upsert(
    {'pneu_id': 'a9346bfa-c582-41b9-aad8-38c156e2f695',
     'url': BASE_URL + '/pneus/metzeler/tourance/110-80-14/dianteiro/video.mp4',
     'tipo': 'video', 'ordem': 3,
     'nome_pneu': 'Metzeler Tourance 110/80-14', 'ativo': True},
    on_conflict='pneu_id,tipo,ordem').execute()
print("OK")
