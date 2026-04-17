"""Processar pasta IRC: WebP + marca d'água"""
import os, io
from dotenv import load_dotenv
from supabase import create_client
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()
load_dotenv(override=True)
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
BASE_URL = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/fotos"
BUCKET = 'fotos'
LOGO_PATH = r'c:\agente-v5-clone\logo_2w.png'
PASTA = r'c:\agente-v5-clone\Pneus\IRC'


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


def upload_e_vincular(filename, storage_path, pneu_id, tipo, ordem, nome_pneu):
    local_path = os.path.join(PASTA, filename)
    print(f"\n{'='*55}")
    print(f"Processando: {filename}")

    data = processar_imagem(local_path)
    print(f"  Imagem: {len(data)/1024:.0f} KB")

    print(f"  Upload → {storage_path} ...", end=" ")
    supabase.storage.from_(BUCKET).upload(storage_path, data, {'content-type': 'image/webp', 'upsert': 'true'})
    print("OK")

    url = f"{BASE_URL}/{storage_path}"
    supabase.table('foto_pneu').upsert(
        {'pneu_id': pneu_id, 'url': url, 'tipo': tipo, 'ordem': ordem,
         'nome_pneu': nome_pneu, 'ativo': True},
        on_conflict='pneu_id,tipo,ordem').execute()
    print("  foto_pneu: OK")


# ── IRC Generico 130/70-13 traseiro ──
upload_e_vincular(
    "Pneu-irc-130-70-13-traseiro-principal-sem câmera.jpg",
    "pneus/irc/generico/130-70-13/traseiro/principal.webp",
    "39a0ee9b-b943-4d8c-8625-45f04e010323", "principal", 1, "IRC Generico 130/70-13"
)
upload_e_vincular(
    "Pneu-irc-130-70-13-traseiro-frontal-sem câmera.jpg",
    "pneus/irc/generico/130-70-13/traseiro/frontal.webp",
    "39a0ee9b-b943-4d8c-8625-45f04e010323", "frontal", 2, "IRC Generico 130/70-13"
)

# ── IRC Generico 130/70-17 traseiro (arquivo nomeado como 140/70-17) ──
upload_e_vincular(
    "Pneu-irc-140-70-17-traseiro-principall-sem câmera",
    "pneus/irc/generico/130-70-17/traseiro/principal.webp",
    "16a25a80-806d-4d3c-b29c-9eb868b3db5e", "principal", 1, "IRC Generico 130/70-17"
)
upload_e_vincular(
    "Pneu-irc-140-70-17-traseiro-frontal-sem câmera.jpg",
    "pneus/irc/generico/130-70-17/traseiro/frontal.webp",
    "16a25a80-806d-4d3c-b29c-9eb868b3db5e", "frontal", 2, "IRC Generico 130/70-17"
)

print(f"\n{'='*55}")
print("IRC concluído!")
