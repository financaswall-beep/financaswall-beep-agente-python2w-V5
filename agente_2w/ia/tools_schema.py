"""Schema das function-calling tools disponibilizadas a IA.

A lista TOOLS_SCHEMA descreve para o modelo cada tool (nome, descricao,
parametros JSON). O dispatcher efetivo que mapeia nome -> callable vive em
`ia/agente.py` porque depende das implementacoes reais.
"""


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "buscar_pneus",
            "description": (
                "Busca pneus no catálogo. "
                "REGRA DE OURO: quando o cliente informar medida com números "
                "(ex: '90/90-18', '90 90 18', '110 80 17'), use SEMPRE "
                "largura + perfil + aro como inteiros separados — NUNCA use "
                "medida_texto para medidas numéricas. "
                "Use medida_texto apenas para entradas NÃO numéricas "
                "(ex: 'pneu aro 17', 'traseiro pirelli'). "
                "Use marca_modelo para busca por nome de marca/modelo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "largura": {"type": "integer", "description": "Largura em mm. Ex: cliente disse '90/90-18' → largura=90"},
                    "perfil": {"type": "integer", "description": "Perfil em %. Ex: cliente disse '90/90-18' → perfil=90"},
                    "aro": {"type": "integer", "description": "Aro em polegadas. Ex: cliente disse '90/90-18' → aro=18"},
                    "medida_texto": {"type": "string", "description": "Use APENAS para entradas NÃO numéricas (ex: 'aro 17', 'pneu traseiro'). Para medidas com 3 números, prefira largura+perfil+aro."},
                    "marca_modelo": {"type": "string", "description": "Nome da marca ou modelo (ex: 'Pirelli', 'Pilot Street')"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_pneus_por_moto",
            "description": "Busca pneus compatíveis com uma moto pelo nome/modelo. Filtre por posicao sempre que souber qual o cliente quer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termo_moto": {"type": "string", "description": "Nome ou modelo da moto (ex: 'CG 160', 'Biz 125')"},
                    "posicao": {"type": "string", "enum": ["dianteiro", "traseiro"], "description": "Posição do pneu. Informe sempre que souber."},
                },
                "required": ["termo_moto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_detalhes_pneu",
            "description": "Busca detalhes completos de um pneu específico pelo UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pneu_id": {"type": "string", "description": "UUID do pneu"},
                },
                "required": ["pneu_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_estoque",
            "description": "Consulta disponibilidade e preço de um pneu específico pelo UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pneu_id": {"type": "string", "description": "UUID do pneu"},
                },
                "required": ["pneu_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolver_cliente",
            "description": "Busca um cliente pelo telefone. Se não existir, cria um novo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "telefone": {"type": "string", "description": "Telefone do cliente (ex: '11999998888')"},
                    "nome": {"type": "string", "description": "Nome do cliente (opcional)"},
                },
                "required": ["telefone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_motos_por_medida",
            "description": "Dado uma medida de pneu (largura/perfil/aro), retorna quais motos usam essa medida e em qual posição (dianteiro/traseiro). Use quando o cliente perguntar 'quais motos usam esse pneu?' ou 'esse pneu serve pra que moto?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "largura": {"type": "integer", "description": "Largura em mm (ex: 140)"},
                    "perfil": {"type": "integer", "description": "Perfil (ex: 70)"},
                    "aro": {"type": "integer", "description": "Aro em polegadas (ex: 17)"},
                    "medida_texto": {"type": "string", "description": "Texto da medida (ex: '140/70-17'). Alternativa a informar largura+perfil+aro."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_catalogo_resumo",
            "description": "Retorna as marcas, medidas e aros disponíveis em estoque. Use quando o cliente perguntar 'que marcas vocês têm?', 'tem aro 17?', 'que medidas tem?', 'o que vocês vendem?'. NUNCA liste marcas ou medidas de memória — use sempre esta tool.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_motos_atendidas",
            "description": "Retorna quais motos possuem pneu em estoque e em quais posições. Use quando o cliente perguntar 'pra que motos vocês têm pneu?', 'tem pra Honda?', 'que motos vocês atendem?'. NUNCA liste motos de memória — use sempre esta tool.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_historico_cliente",
            "description": "Retorna os últimos pedidos de um cliente. Use quando o cliente perguntar 'qual foi meu último pedido?', 'quero o mesmo de antes', 'já comprei aqui?'. Necessita do cliente_id (disponível no contexto após resolução do cliente).",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {"type": "string", "description": "UUID do cliente (do contexto da sessão)"},
                    "limite": {"type": "integer", "description": "Quantidade máxima de pedidos (default: 5)"},
                },
                "required": ["cliente_id"],
            },
        },
    },
]

# Nomes de tools que retornam pneu_id (para auto-enriquecimento downstream)
TOOLS_COM_PNEU = {
    "buscar_pneus",
    "buscar_pneus_por_moto",
    "buscar_detalhes_pneu",
    "consultar_estoque",
}
