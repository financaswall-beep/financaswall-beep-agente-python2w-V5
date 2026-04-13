"""Teste da Fase 5 — IA (prompt, agente, parser)."""
import sys
sys.path.insert(0, ".")

resultados = []

def teste(nome, fn):
    try:
        r = fn()
        resultados.append(("PASS", nome))
        return r
    except Exception as e:
        resultados.append(("FAIL", nome, str(e)[:200]))
        return None

print("=" * 60)
print("TESTE FASE 5: IA")
print("=" * 60)

# --- GRUPO 1: Imports ---
print("\n--- Imports ---")

def test_import_prompt():
    from agente_2w.ia.prompt_sistema import SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) > 500, "prompt muito curto"
    assert "2W Pneus" in SYSTEM_PROMPT
    assert "EnvelopeIA" in SYSTEM_PROMPT
    return len(SYSTEM_PROMPT)

r = teste("import prompt_sistema", test_import_prompt)
if r:
    print(f"  -> prompt com {r} caracteres")

def test_import_agente():
    from agente_2w.ia.agente import chamar_agente, TOOLS_SCHEMA, _TOOL_DISPATCH
    assert len(TOOLS_SCHEMA) == 5, f"esperava 5 tools, tem {len(TOOLS_SCHEMA)}"
    assert len(_TOOL_DISPATCH) == 5
    return True

teste("import agente (5 tools)", test_import_agente)

def test_import_parser():
    from agente_2w.ia.parser_envelope import parse_resposta, ParseError
    return True

teste("import parser_envelope", test_import_parser)

# --- GRUPO 2: Parser ---
print("\n--- Parser ---")

from agente_2w.ia.parser_envelope import parse_resposta, ParseError
from agente_2w.enums.enums import EtapaFluxo
from agente_2w.schemas.contexto_executavel import (
    ContextoExecutavel, SessaoContexto, ClienteContexto, Metadados,
)
from datetime import datetime, timezone

# Helper: contexto minimo para testes do parser
def _ctx(etapa=EtapaFluxo.identificacao):
    return ContextoExecutavel(
        sessao=SessaoContexto(
            sessao_id="00000000-0000-0000-0000-000000000000",
            canal="teste",
            contato_externo="teste",
            etapa_atual=etapa,
            status_sessao="ativa",
            ultima_interacao_em=datetime.now(timezone.utc),
        ),
        cliente=ClienteContexto(),
        metadados=Metadados(gerado_em=datetime.now(timezone.utc)),
    )

# JSON valido
json_valido = '''{
  "mensagem_cliente": "Oi! Qual moto voce tem?",
  "etapa_atual": "identificacao",
  "intencao_atual": "saudacao inicial",
  "acoes_sugeridas": ["pedir_clarificacao_moto"],
  "pendencias": ["moto_ou_medida"],
  "confianca": "alta",
  "fatos_observados": [],
  "fatos_inferidos": [],
  "mudancas_contexto": [],
  "mudancas_itens": [],
  "bloqueios_identificados": []
}'''

def test_parse_valido():
    envelope, erros = parse_resposta(json_valido, _ctx())
    assert envelope.mensagem_cliente == "Oi! Qual moto voce tem?"
    assert envelope.etapa_atual == EtapaFluxo.identificacao
    return len(erros)

r = teste("parse JSON valido", test_parse_valido)
if r is not None:
    print(f"  -> {r} erros de validacao")

# JSON com markdown
json_markdown = '```json\n' + json_valido + '\n```'

def test_parse_markdown():
    envelope, erros = parse_resposta(json_markdown, _ctx())
    assert envelope.mensagem_cliente == "Oi! Qual moto voce tem?"
    return True

teste("parse JSON envolto em markdown", test_parse_markdown)

# JSON com texto antes
json_com_lixo = 'Aqui esta minha resposta:\n\n' + json_valido + '\n\nObrigado!'

def test_parse_com_lixo():
    envelope, erros = parse_resposta(json_com_lixo, _ctx())
    assert envelope.mensagem_cliente == "Oi! Qual moto voce tem?"
    return True

teste("parse JSON com texto ao redor", test_parse_com_lixo)

# JSON invalido
def test_parse_invalido():
    try:
        parse_resposta("isso nao e json", _ctx())
        return False  # deveria ter dado erro
    except ParseError:
        return True

r = teste("parse rejeita texto invalido", test_parse_invalido)
if r:
    print("  -> ParseError levantado corretamente")

# Validacao de acao invalida
json_acao_errada = '''{
  "mensagem_cliente": "Pedido confirmado!",
  "etapa_atual": "identificacao",
  "intencao_atual": "fechar pedido",
  "acoes_sugeridas": ["converter_em_pedido"],
  "confianca": "alta"
}'''

def test_validacao_acao():
    envelope, erros = parse_resposta(json_acao_errada, _ctx())
    assert len(erros) > 0, "deveria ter erros de validacao"
    return erros

r = teste("parse detecta acao invalida na etapa", test_validacao_acao)
if r:
    print(f"  -> erros: {r}")

# --- GRUPO 3: Chamada real ao OpenAI ---
print("\n--- Chamada real ao OpenAI ---")

from agente_2w.ia.agente import chamar_agente
from agente_2w.engine.montador_contexto import montar_contexto
from agente_2w.db import sessao_repo
from agente_2w.schemas.sessao_chat import SessaoChatCreate
from agente_2w.enums.enums import StatusSessao

# Criar sessao temporaria para ter um contexto real
sessao = sessao_repo.criar_sessao(SessaoChatCreate(
    canal="teste_fase5",
    contato_externo="teste_fase5_bot",
    etapa_atual=EtapaFluxo.identificacao,
    status_sessao=StatusSessao.ativa,
))
print(f"  sessao teste: {sessao.id}")

ctx = montar_contexto(sessao.id)

def test_chamada_openai():
    resposta_bruta = chamar_agente(ctx, "Oi, preciso de um pneu pra minha CG 160")
    assert len(resposta_bruta) > 10, "resposta vazia"
    return resposta_bruta

r = teste("chamar_agente (OpenAI real)", test_chamada_openai)
if r:
    print(f"  -> resposta: {r[:150]}...")

# Tentar parsear a resposta real
if r:
    def test_parse_resposta_real():
        envelope, erros = parse_resposta(r, ctx)
        return envelope, erros

    resultado = teste("parse resposta real da IA", test_parse_resposta_real)
    if resultado:
        envelope, erros = resultado
        print(f"  -> etapa: {envelope.etapa_atual}")
        print(f"  -> intencao: {envelope.intencao_atual}")
        print(f"  -> acoes: {envelope.acoes_sugeridas}")
        print(f"  -> fatos_obs: {len(envelope.fatos_observados)}")
        print(f"  -> erros validacao: {erros}")
        print(f"  -> msg: {envelope.mensagem_cliente[:100]}...")

# Limpar dados de teste
from agente_2w.db.client import supabase
supabase.table("sessao_chat").delete().eq("id", str(sessao.id)).execute()
print("  -> sessao de teste removida")

# --- RELATORIO ---
print("\n" + "=" * 60)
print("RELATORIO FASE 5")
print("=" * 60)
total = len(resultados)
passed = sum(1 for r in resultados if r[0] == "PASS")
failed = sum(1 for r in resultados if r[0] == "FAIL")
for r in resultados:
    mark = "V" if r[0] == "PASS" else "X"
    print(f"  {mark} {r[1]}")
    if r[0] == "FAIL":
        print(f"    ERRO: {r[2]}")
print(f"\nTotal: {total} | PASS: {passed} | FAIL: {failed}")
if failed == 0:
    print("TODOS OS TESTES PASSARAM")
else:
    print(f"{failed} FALHA(S)")
