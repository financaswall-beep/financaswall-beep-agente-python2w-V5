"""
Processa uma pasta por vez:
- Converte HEIC/JPG → WebP com marca d'água
- Comprime vídeos MOV/MP4 para < 16MB com marca d'água
- Sobe no storage substituindo arquivos antigos
- Atualiza URLs na foto_pneu
- Remove arquivos antigos do storage
"""
import os, io, subprocess, tempfile
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from PIL import Image
from pillow_heif import register_heif_opener
import imageio_ffmpeg

register_heif_opener()
load_dotenv(override=True)

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
BASE_URL = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/fotos"
BUCKET = "fotos"
LOGO_PATH = r"c:\agente-v5-clone\logo_2w.png"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# ─── Mapeamento: Vipal, Technic, Metzeler ────────────────────────────────────
# (local, storage_novo, storage_antigos_p_apagar, pneu_id, tipo, ordem, nome)
UPLOADS = [
    # ── Vipal ST 600 80/100-18 dianteiro ──
    (
        r"Pneus\Vipal\Pneu-Vipal-Street -st300-80-100-18-dianteiro-frontal",
        "pneus/vipal/st-600/80-100-18/dianteiro/frontal.webp",
        ["pneus/vipal/st-600/80-100-18/dianteiro/frontal.heic"],
        "ca6ccf93-e580-42df-8399-a301291fdb05", "frontal", 2, "Vipal ST 600 80/100-18",
    ),
    (
        r"Pneus\Vipal\Pneu-Vipal-Street -st300-80-100-18-dianteiro-principal.jpg",
        "pneus/vipal/st-600/80-100-18/dianteiro/principal.webp",
        ["pneus/vipal/st-600/80-100-18/dianteiro/principal.jpg"],
        "ca6ccf93-e580-42df-8399-a301291fdb05", "principal", 1, "Vipal ST 600 80/100-18",
    ),
    # ── Vipal ST 500 140/70-17 traseiro ──
    (
        r"Pneus\Vipal\Pneu-vipal-street-st500-140-70-17-traseiro-sem câmara-frontal.jpg",
        "pneus/vipal/st-500/140-70-17/traseiro/frontal.webp",
        ["pneus/vipal/st-500/140-70-17/traseiro/frontal.jpg"],
        "5882d64d-8640-4f90-b2b6-e8075ca609be", "frontal", 2, "Vipal ST 500 140/70-17",
    ),
    (
        r"Pneus\Vipal\Pneu-vipal-street-st500-140-70-17-traseiro-sem câmara-principal.jpg",
        "pneus/vipal/st-500/140-70-17/traseiro/principal.webp",
        ["pneus/vipal/st-500/140-70-17/traseiro/principal.jpg"],
        "5882d64d-8640-4f90-b2b6-e8075ca609be", "principal", 1, "Vipal ST 500 140/70-17",
    ),
    # ── Technic Scooter 130/70-13 traseiro ──
    (
        r"Pneus\Technic\Pneu-Technic-130-17-13-traseiro-frontal-sem câmara.jpg",
        "pneus/technic/scooter/130-70-13/traseiro/frontal.webp",
        ["pneus/technic/scooter/130-70-13/traseiro/frontal.jpg"],
        "65af32ad-caa6-4f27-b6ae-81577d2a613f", "frontal", 2, "Technic Scooter 130/70-13",
    ),
    (
        r"Pneus\Technic\Pneu-Technic-130-17-13-traseiro-principal-sem câmara.jpg",
        "pneus/technic/scooter/130-70-13/traseiro/principal.webp",
        ["pneus/technic/scooter/130-70-13/traseiro/principal.jpg"],
        "65af32ad-caa6-4f27-b6ae-81577d2a613f", "principal", 1, "Technic Scooter 130/70-13",
    ),
    # ── Metzeler Sportec 120/70-15 dianteiro ──
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-120-70-15-dianteiro-frontal.jpg",
        "pneus/metzeler/sportec/120-70-15/dianteiro/frontal.webp",
        ["pneus/metzeler/sportec/120-70-15/dianteiro/frontal.jpg"],
        "40bfd4c1-f6f9-4353-9174-7efa2a71671c", "frontal", 2, "Metzeler Sportec 120/70-15",
    ),
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-120-70-15-dianteiro-principal.jpg",
        "pneus/metzeler/sportec/120-70-15/dianteiro/principal.webp",
        ["pneus/metzeler/sportec/120-70-15/dianteiro/principal.jpg"],
        "40bfd4c1-f6f9-4353-9174-7efa2a71671c", "principal", 1, "Metzeler Sportec 120/70-15",
    ),
    # ── Metzeler Interact 140/70-17 traseiro ──
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-140-70-17-traseiro-frontal-sem câmera.jpg",
        "pneus/metzeler/interact/140-70-17/traseiro/frontal.webp",
        ["pneus/metzeler/interact/140-70-17/traseiro/frontal.jpg"],
        "4f5e59f6-34da-41af-b47e-e8cb5d37e7f6", "frontal", 2, "Metzeler Interact 140/70-17",
    ),
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-140-70-17-trasero-principal-sem câmera.jpg",
        "pneus/metzeler/interact/140-70-17/traseiro/principal.webp",
        ["pneus/metzeler/interact/140-70-17/traseiro/principal.jpg"],
        "4f5e59f6-34da-41af-b47e-e8cb5d37e7f6", "principal", 1, "Metzeler Interact 140/70-17",
    ),
    # ── Metzeler Tourance 110/80-14 dianteiro ──
    (
        r"Pneus\Meltzeller\Pneu-metzeller-tourance-110-80-14-dianteiro-sem câmera-frontal",
        "pneus/metzeler/tourance/110-80-14/dianteiro/frontal.webp",
        ["pneus/metzeler/tourance/110-80-14/dianteiro/frontal.heic"],
        "a9346bfa-c582-41b9-aad8-38c156e2f695", "frontal", 2, "Metzeler Tourance 110/80-14",
    ),
    (
        r"Pneus\Meltzeller\Pneu-metzeller-tourance-110-80-14-dianteiro-sem câmera-principal",
        "pneus/metzeler/tourance/110-80-14/dianteiro/principal.webp",
        ["pneus/metzeler/tourance/110-80-14/dianteiro/principal.heic"],
        "a9346bfa-c582-41b9-aad8-38c156e2f695", "principal", 1, "Metzeler Tourance 110/80-14",
    ),
    (
        r"Pneus\Meltzeller\Pneu-metzeller-tourance-110-80-14-dianteiro-sem câmera-vídeo.mov",
        "pneus/metzeler/tourance/110-80-14/dianteiro/video.mp4",
        ["pneus/metzeler/tourance/110-80-14/dianteiro/video.mov"],
        "a9346bfa-c582-41b9-aad8-38c156e2f695", "video", 3, "Metzeler Tourance 110/80-14",
    ),
]


def adicionar_marca_dagua(img: Image.Image) -> Image.Image:
    logo = Image.open(LOGO_PATH).convert("RGBA")
    # Redimensiona logo para 22% da largura da imagem
    w_logo = max(80, int(img.width * 0.22))
    ratio = w_logo / logo.width
    h_logo = int(logo.height * ratio)
    logo = logo.resize((w_logo, h_logo), Image.LANCZOS)
    # Aplica transparência de 70%
    r, g, b, a = logo.split()
    a = a.point(lambda x: int(x * 0.70))
    logo.putalpha(a)
    # Posição: canto inferior direito com margem 15px
    base = img.convert("RGBA")
    pos = (img.width - w_logo - 15, img.height - h_logo - 15)
    base.paste(logo, pos, logo)
    return base.convert("RGB")


def processar_imagem(local_path: str) -> bytes:
    img = Image.open(local_path)
    img = adicionar_marca_dagua(img)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=82)
    return buf.getvalue()


def processar_video(local_path: str) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_out = tmp.name

    # Redimensiona logo para arquivo temporário PNG para usar no filtro ffmpeg
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_logo:
        tmp_logo_path = tmp_logo.name
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo = logo.resize((160, 160), Image.LANCZOS)
    logo.save(tmp_logo_path, format="PNG")

    logo_filt = tmp_logo_path.replace('\\', '/')
    cmd = [
        FFMPEG, "-y", "-i", local_path,
        "-i", tmp_logo_path,
        "-filter_complex", "[1:v]scale=160:-1,format=rgba,colorchannelmixer=aa=0.7[wm];[0:v][wm]overlay=W-w-15:H-h-15",
        "-c:v", "libx264", "-crf", "28", "-preset", "fast",
        "-c:a", "aac", "-b:a", "96k",
        tmp_out
    ]
    result = subprocess.run(cmd, capture_output=True)
    os.unlink(tmp_logo_path)
    if result.returncode != 0:
        # fallback sem marca d'água
        print(f"    Aviso: overlay falhou, comprimindo sem marca d'água")
        cmd2 = [
            FFMPEG, "-y", "-i", local_path,
            "-c:v", "libx264", "-crf", "28", "-preset", "fast",
            "-c:a", "aac", "-b:a", "96k",
            tmp_out
        ]
        subprocess.run(cmd2, capture_output=True)

    with open(tmp_out, "rb") as f:
        data = f.read()
    os.unlink(tmp_out)
    size_mb = len(data) / 1024 / 1024
    print(f"    Vídeo comprimido: {size_mb:.1f} MB")
    return data


def deletar_storage(paths: list[str]):
    for p in paths:
        try:
            supabase.storage.from_(BUCKET).remove([p])
            print(f"    Deletado: {p}")
        except Exception as e:
            print(f"    Aviso ao deletar {p}: {e}")


def main():
    for item in UPLOADS:
        local_path, storage_new, storage_old, pneu_id, tipo, ordem, nome_pneu = item
        local_file = Path(local_path)

        if not local_file.exists():
            print(f"[ERRO] Não encontrado: {local_file.name}")
            continue

        print(f"\n{'='*60}")
        print(f"Processando: {local_file.name}")

        is_video = storage_new.endswith(".mp4")

        # 1. Processar arquivo
        if is_video:
            print("  Comprimindo vídeo + marca d'água...")
            data = processar_video(str(local_file))
            mime = "video/mp4"
        else:
            print("  Convertendo para WebP + marca d'água...")
            data = processar_imagem(str(local_file))
            mime = "image/webp"

        # 2. Upload novo arquivo
        print(f"  Upload → {storage_new} ...", end=" ")
        try:
            supabase.storage.from_(BUCKET).upload(
                path=storage_new,
                file=data,
                file_options={"content-type": mime, "upsert": "true"},
            )
            print("OK")
        except Exception as e:
            print(f"ERRO: {e}")
            continue

        # 3. Atualizar foto_pneu
        url = f"{BASE_URL}/{storage_new}"
        print(f"  Atualizando foto_pneu ...", end=" ")
        try:
            supabase.table("foto_pneu").upsert(
                {"pneu_id": pneu_id, "url": url, "tipo": tipo, "ordem": ordem,
                 "nome_pneu": nome_pneu, "ativo": True},
                on_conflict="pneu_id,tipo,ordem",
            ).execute()
            print("OK")
        except Exception as e:
            print(f"ERRO: {e}")

        # 4. Deletar arquivos antigos
        deletar_storage(storage_old)

    print(f"\n{'='*60}")
    print("Concluído!")


if __name__ == "__main__":
    main()
