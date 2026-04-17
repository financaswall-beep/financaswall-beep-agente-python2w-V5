"""
Script para upload das fotos Vipal ao storage e vínculo na tabela foto_pneu.
"""
import os
import mimetypes
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)

# service_role para uploads (bypassa RLS do storage)
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

BASE_URL = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/fotos"
BUCKET = "fotos"

# Mapeamento: (arquivo_local, storage_path, pneu_id, tipo, ordem, descricao, nome_pneu)
UPLOADS = [
    # Metzeler Sportec 120/70-15 dianteiro
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-120-70-15-dianteiro-frontal.jpg",
        "pneus/metzeler/sportec/120-70-15/dianteiro/frontal.jpg",
        "40bfd4c1-f6f9-4353-9174-7efa2a71671c",
        "frontal", 2, "Vista frontal", "Metzeler Sportec 120/70-15",
        "image/jpeg",
    ),
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-120-70-15-dianteiro-principal.jpg",
        "pneus/metzeler/sportec/120-70-15/dianteiro/principal.jpg",
        "40bfd4c1-f6f9-4353-9174-7efa2a71671c",
        "principal", 1, "Foto principal", "Metzeler Sportec 120/70-15",
        "image/jpeg",
    ),
    # Metzeler Interact 140/70-17 traseiro
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-140-70-17-traseiro-frontal-sem câmera.jpg",
        "pneus/metzeler/interact/140-70-17/traseiro/frontal.jpg",
        "4f5e59f6-34da-41af-b47e-e8cb5d37e7f6",
        "frontal", 2, "Vista frontal sem câmara", "Metzeler Interact 140/70-17",
        "image/jpeg",
    ),
    (
        r"Pneus\Meltzeller\Pneu-Metzeller-140-70-17-trasero-principal-sem câmera.jpg",
        "pneus/metzeler/interact/140-70-17/traseiro/principal.jpg",
        "4f5e59f6-34da-41af-b47e-e8cb5d37e7f6",
        "principal", 1, "Foto principal sem câmara", "Metzeler Interact 140/70-17",
        "image/jpeg",
    ),
    # Metzeler Tourance 110/80-14 dianteiro
    (
        r"Pneus\Meltzeller\Pneu-metzeller-tourance-110-80-14-dianteiro-sem câmera-frontal",
        "pneus/metzeler/tourance/110-80-14/dianteiro/frontal.heic",
        "a9346bfa-c582-41b9-aad8-38c156e2f695",
        "frontal", 2, "Vista frontal sem câmara", "Metzeler Tourance 110/80-14",
        "image/heic",
    ),
    (
        r"Pneus\Meltzeller\Pneu-metzeller-tourance-110-80-14-dianteiro-sem câmera-principal",
        "pneus/metzeler/tourance/110-80-14/dianteiro/principal.heic",
        "a9346bfa-c582-41b9-aad8-38c156e2f695",
        "principal", 1, "Foto principal sem câmara", "Metzeler Tourance 110/80-14",
        "image/heic",
    ),
    (
        r"Pneus\Meltzeller\Pneu-metzeller-tourance-110-80-14-dianteiro-sem câmera-vídeo.mov",
        "pneus/metzeler/tourance/110-80-14/dianteiro/video.mov",
        "a9346bfa-c582-41b9-aad8-38c156e2f695",
        "video", 3, "Vídeo do pneu", "Metzeler Tourance 110/80-14",
        "video/quicktime",
    ),
    # Technic Scooter 130/70-13 traseiro
    (
        r"Pneus\Technic\Pneu-Technic-130-17-13-traseiro-frontal-sem câmara.jpg",
        "pneus/technic/scooter/130-70-13/traseiro/frontal.jpg",
        "65af32ad-caa6-4f27-b6ae-81577d2a613f",
        "frontal", 2, "Vista frontal sem câmara", "Technic Scooter 130/70-13",
        "image/jpeg",
    ),
    (
        r"Pneus\Technic\Pneu-Technic-130-17-13-traseiro-principal-sem câmara.jpg",
        "pneus/technic/scooter/130-70-13/traseiro/principal.jpg",
        "65af32ad-caa6-4f27-b6ae-81577d2a613f",
        "principal", 1, "Foto principal sem câmara", "Technic Scooter 130/70-13",
        "image/jpeg",
    ),
    # Vipal ST 600 80/100-18 dianteiro  (arquivo nomeado como ST300 mas ST300 não existe no banco)
    (
        r"Pneus\Vipal\Pneu-Vipal-Street -st300-80-100-18-dianteiro-frontal",
        "pneus/vipal/st-600/80-100-18/dianteiro/frontal.heic",
        "ca6ccf93-e580-42df-8399-a301291fdb05",
        "frontal", 2, "Vista frontal", "Vipal ST 600 80/100-18",
        "image/heic",
    ),
    (
        r"Pneus\Vipal\Pneu-Vipal-Street -st300-80-100-18-dianteiro-principal.jpg",
        "pneus/vipal/st-600/80-100-18/dianteiro/principal.jpg",
        "ca6ccf93-e580-42df-8399-a301291fdb05",
        "principal", 1, "Foto principal", "Vipal ST 600 80/100-18",
        "image/jpeg",
    ),
    # Vipal ST 500 140/70-17 traseiro
    (
        r"Pneus\Vipal\Pneu-vipal-street-st500-140-70-17-traseiro-sem câmara-frontal.jpg",
        "pneus/vipal/st-500/140-70-17/traseiro/frontal.jpg",
        "5882d64d-8640-4f90-b2b6-e8075ca609be",
        "frontal", 2, "Vista frontal", "Vipal ST 500 140/70-17",
        "image/jpeg",
    ),
    (
        r"Pneus\Vipal\Pneu-vipal-street-st500-140-70-17-traseiro-sem câmara-principal.jpg",
        "pneus/vipal/st-500/140-70-17/traseiro/principal.jpg",
        "5882d64d-8640-4f90-b2b6-e8075ca609be",
        "principal", 1, "Foto principal", "Vipal ST 500 140/70-17",
        "image/jpeg",
    ),
]

def upload_and_link():
    for local_path, storage_path, pneu_id, tipo, ordem, descricao, nome_pneu, mime in UPLOADS:
        local_file = Path(local_path)
        if not local_file.exists():
            print(f"[ERRO] Arquivo não encontrado: {local_file}")
            continue

        print(f"Uploading {local_file.name} → {storage_path} ...", end=" ")
        with open(local_file, "rb") as f:
            data = f.read()

        try:
            res = supabase.storage.from_(BUCKET).upload(
                path=storage_path,
                file=data,
                file_options={"content-type": mime, "upsert": "true"},
            )
            print("OK")
        except Exception as e:
            print(f"ERRO no upload: {e}")
            continue

        url = f"{BASE_URL}/{storage_path}"
        print(f"  Inserindo em foto_pneu: tipo={tipo} ordem={ordem} ...", end=" ")
        try:
            supabase.table("foto_pneu").upsert(
                {
                    "pneu_id": pneu_id,
                    "url": url,
                    "tipo": tipo,
                    "ordem": ordem,
                    "descricao": descricao,
                    "nome_pneu": nome_pneu,
                    "ativo": True,
                },
                on_conflict="pneu_id,tipo,ordem",
            ).execute()
            print("OK")
        except Exception as e:
            print(f"ERRO no insert: {e}")

    print("\nConcluído.")

if __name__ == "__main__":
    upload_and_link()
