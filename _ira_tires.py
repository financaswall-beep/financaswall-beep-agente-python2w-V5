"""Processar pasta Irá tires: WebP + marca d'água"""
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
PASTA = r'c:\agente-v5-clone\Pneus\Irá tires'


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


# ── Inserir pneu Irá Tires Generico 140/70-17 ──
print("Inserindo pneu Irá Tires 140/70-17...")
resp = supabase.table('pneu').insert({
    'marca': 'Irá Tires',
    'modelo': 'Generico',
    'medida': '140/70-17',
    'aro': 17,
    'largura': 140,
    'perfil': 70,
    'descricao_comercial': 'Irá Tires Generico 140/70-17',
    'ativo': True,
}).execute()
pneu_id = resp.data[0]['id']
print(f"  pneu_id: {pneu_id}")

# ── Irá Tires 140/70-17 traseiro ──
upload_e_vincular(
    'Pneu-ira-tires-140-70-17-traseiro-sem câmara-principal.jpg',
    'pneus/ira-tires/generico/140-70-17/traseiro/principal.webp',
    pneu_id, 'principal', 1, 'Irá Tires Generico 140/70-17'
)
upload_e_vincular(
    'Pneu-iIra-Tires-140-70-17-traseiro-frontal-sem câmara.jpg',
    'pneus/ira-tires/generico/140-70-17/traseiro/frontal.webp',
    pneu_id, 'frontal', 2, 'Irá Tires Generico 140/70-17'
)

print("\n\nIrá Tires: CONCLUÍDO!")
