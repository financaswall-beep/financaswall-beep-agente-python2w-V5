"""
Teste B3 — resolver_ou_criar_cliente atômico.

Verifica dois cenários:
1. Chamada simples: cria cliente novo e retorna o mesmo em chamada repetida
2. Concorrência: N threads simultâneas para o mesmo telefone → exatamente 1 registro

Executa contra o Supabase real (banco de teste/desenvolvimento).
"""
import concurrent.futures
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agente_2w.db import cliente_repo
from agente_2w.db.client import supabase

TELEFONE_TESTE = "5521000000001"


def _limpar():
    supabase.table("cliente").delete().eq("telefone", TELEFONE_TESTE).execute()


def test_cria_cliente_novo():
    _limpar()
    cliente = cliente_repo.resolver_ou_criar_cliente(TELEFONE_TESTE, "Teste B3")
    assert cliente.telefone == TELEFONE_TESTE, "telefone incorreto"
    assert cliente.id is not None, "id nulo"
    print(f"  [OK] Cliente criado: id={cliente.id}, telefone={cliente.telefone}")


def test_retorna_existente_se_repetido():
    # Banco já tem o registro do teste anterior
    c1 = cliente_repo.resolver_ou_criar_cliente(TELEFONE_TESTE, "Qualquer Nome")
    c2 = cliente_repo.resolver_ou_criar_cliente(TELEFONE_TESTE, "Outro Nome")
    assert c1.id == c2.id, f"IDs diferentes! c1={c1.id} c2={c2.id}"
    print(f"  [OK] Mesmo ID retornado em ambas as chamadas: {c1.id}")


def test_concorrencia_sem_duplicata():
    _limpar()

    resultados = []

    def chamar(i):
        return cliente_repo.resolver_ou_criar_cliente(TELEFONE_TESTE, f"Worker {i}")

    # 10 threads simultâneas tentando criar o mesmo telefone
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(chamar, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            resultados.append(f.result())

    ids = {str(r.id) for r in resultados}
    assert len(ids) == 1, f"FALHOU: {len(ids)} IDs diferentes criados! {ids}"

    # Confirma no banco que só existe 1 registro
    rows = supabase.table("cliente").select("id").eq("telefone", TELEFONE_TESTE).execute()
    assert len(rows.data) == 1, f"FALHOU: {len(rows.data)} registros no banco!"

    print(f"  [OK] 10 workers simultâneos → 1 único registro. ID={list(ids)[0]}")


def main():
    print("\n=== Teste B3: resolver_ou_criar_cliente atômico ===\n")

    try:
        print("1. Criação de cliente novo...")
        test_cria_cliente_novo()

        print("2. Retorno do existente em chamada repetida...")
        test_retorna_existente_se_repetido()

        print("3. Concorrência: 10 threads no mesmo telefone...")
        test_concorrencia_sem_duplicata()

        print("\n✓ Todos os testes passaram.\n")
    except AssertionError as e:
        print(f"\n✗ FALHOU: {e}\n")
        sys.exit(1)
    finally:
        _limpar()
        print("(registro de teste removido do banco)")


if __name__ == "__main__":
    main()
