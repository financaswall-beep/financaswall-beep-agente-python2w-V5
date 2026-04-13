# Implementacao V1 — Guia de Codigo

## Objetivo

Transformar a documentacao conceitual e o banco `betaAgente` em codigo Python funcional.

Este documento define:

- estrutura de pastas do projeto;
- stack tecnica;
- schemas Pydantic refletindo o banco;
- orquestrador e maquina de estados;
- tools de leitura;
- integracao com a IA;
- conversao em pedido;
- ordem de implementacao com dependencias.

O codigo deve refletir fielmente o banco implementado no Supabase e os contratos definidos nos documentos anteriores.

## Stack tecnica

| Camada | Tecnologia | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | compatibilidade com tipagem moderna e Pydantic v2 |
| Schemas e validacao | Pydantic v2 | validacao estrutural do envelope da IA, contexto e entidades |
| Banco | Supabase (PostgreSQL 17) | banco `betaAgente`, projeto `vyxdquwxmgibpkoswxut` |
| Cliente do banco | `supabase-py` | SDK oficial para Python |
| IA | OpenAI SDK (`openai`) + `tenacity` | GPT-4o com function calling, response_format=json_object, retry com backoff |
| Servidor HTTP | FastAPI (futuro) | API para receber webhooks do WhatsApp, fora do V1 inicial |
| Variáveis de ambiente | `python-dotenv` | chaves de API e configuracao |

> **Nota (29/03/2026):** O modelo original era Claude/Anthropic. A implementacao final usa OpenAI GPT-4o por decisao durante o desenvolvimento. O SDK e `openai`, nao `anthropic`.

## Estrutura de pastas

```
agente_2w/
├── __init__.py
├── main.py                          # ponto de entrada CLI para testes
├── config.py                        # configuracao e variaveis de ambiente
├── constantes.py                    # chaves de contexto centralizadas (ChaveContexto)
│
├── enums/
│   ├── __init__.py
│   └── enums.py                     # todos os enums do banco
│
├── schemas/
│   ├── __init__.py
│   ├── cliente.py                   # schema de cliente
│   ├── sessao_chat.py               # schema de sessao
│   ├── mensagem_chat.py             # schema de mensagem
│   ├── contexto_conversa.py         # schema de contexto (fato)
│   ├── item_provisorio.py           # schema de item provisorio
│   ├── pneu.py                      # schema de pneu
│   ├── moto.py                      # schema de moto
│   ├── medida_moto.py               # schema de medida por moto
│   ├── estoque.py                   # schema de estoque
│   ├── pedido.py                    # schema de pedido
│   ├── item_pedido.py               # schema de item pedido
│   ├── endereco_entrega.py          # schema Pydantic do jsonb de endereco
│   ├── metadata_chat.py             # schema Pydantic do jsonb de metadata
│   ├── contexto_executavel.py       # payload completo entregue a IA
│   └── envelope_ia.py               # resposta estruturada da IA
│
├── db/
│   ├── __init__.py
│   ├── client.py                    # cliente Supabase (com deteccao de proxy Windows)
│   ├── exceptions.py                # excecoes tipadas (RepositoryError, etc.)
│   ├── sessao_repo.py               # operacoes de sessao_chat
│   ├── mensagem_repo.py             # operacoes de mensagem_chat
│   ├── contexto_repo.py             # operacoes de contexto_conversa
│   ├── item_provisorio_repo.py      # operacoes de item_provisorio
│   ├── cliente_repo.py              # operacoes de cliente
│   ├── catalogo_repo.py             # operacoes de pneu + estoque + moto + medida_moto + views
│   ├── pedido_repo.py               # operacoes de pedido + item_pedido
│   └── queries.py                   # queries auxiliares reutilizaveis
│
├── engine/
│   ├── __init__.py
│   ├── maquina_estados.py           # transicoes permitidas e bloqueios
│   ├── orquestrador.py              # loop principal de um turno (13 passos + retry)
│   ├── montador_contexto.py         # monta o contexto executavel do turno
│   ├── validador_envelope.py        # valida o envelope de saida da IA
│   ├── promotor.py                  # promove itens via RPC transacional
│   └── pendencias.py                # calcula pendencias por etapa
│
├── tools/
│   ├── __init__.py
│   ├── busca_catalogo.py            # busca pneu por dimensoes, moto, marca (usa views)
│   ├── consulta_estoque.py          # consulta disponibilidade e preco
│   └── resolve_cliente.py           # resolve ou cria cliente por telefone
│
└── ia/
    ├── __init__.py
    ├── agente.py                    # chamada ao Claude com contexto
    ├── prompt_sistema.py            # system prompt do agente
    └── parser_envelope.py           # parse e validacao da resposta da IA
```

## Enums Python

Devem refletir exatamente os enums do banco. Usar `str, Enum` para compatibilidade com Pydantic e JSON.

```python
# agente_2w/enums/enums.py

from enum import Enum

class TipoDeVerdade(str, Enum):
    observado = "observado"
    inferido = "inferido"
    validado_tool = "validado_tool"
    confirmado_cliente = "confirmado_cliente"
    validado_backend = "validado_backend"
    oficializado = "oficializado"

class EtapaFluxo(str, Enum):
    identificacao = "identificacao"
    busca = "busca"
    oferta = "oferta"
    confirmacao_item = "confirmacao_item"
    entrega_pagamento = "entrega_pagamento"
    fechamento = "fechamento"

class StatusSessao(str, Enum):
    ativa = "ativa"
    aguardando_cliente = "aguardando_cliente"
    bloqueada = "bloqueada"
    fechada = "fechada"

class NivelConfirmacao(str, Enum):
    nenhum = "nenhum"
    confirmado_cliente = "confirmado_cliente"
    validado_tool = "validado_tool"
    validado_backend = "validado_backend"
    oficializado = "oficializado"

class OrigemContexto(str, Enum):
    mensagem_cliente = "mensagem_cliente"
    inferido_ia = "inferido_ia"
    tool = "tool"
    backend = "backend"
    operador = "operador"
    sistema = "sistema"

class StatusItemProvisorio(str, Enum):
    sugerido = "sugerido"
    selecionado_cliente = "selecionado_cliente"
    validado = "validado"
    rejeitado = "rejeitado"
    cancelado = "cancelado"
    promovido = "promovido"

class TipoEntrega(str, Enum):
    retirada = "retirada"
    entrega = "entrega"
    a_confirmar = "a_confirmar"

class FormaPagamento(str, Enum):
    pix = "pix"
    dinheiro = "dinheiro"
    cartao = "cartao"
    transferencia = "transferencia"
    a_confirmar = "a_confirmar"

class StatusPedido(str, Enum):
    confirmado = "confirmado"
    cancelado = "cancelado"
    entregue = "entregue"

class Confianca(str, Enum):
    alta = "alta"
    media = "media"
    baixa = "baixa"

class Direcao(str, Enum):
    entrada = "entrada"
    saida = "saida"

class Remetente(str, Enum):
    cliente = "cliente"
    agente = "agente"
    operador = "operador"

class Posicao(str, Enum):
    dianteiro = "dianteiro"
    traseiro = "traseiro"
    par = "par"
```

## Schemas Pydantic — Entidades do banco

Cada schema reflete uma tabela. Schemas de leitura e de escrita sao separados quando necessario.

### `cliente.py`

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional

class ClienteBase(BaseModel):
    telefone: str
    nome: Optional[str] = None
    documento: Optional[str] = None

class ClienteCreate(ClienteBase):
    pass

class Cliente(ClienteBase):
    id: UUID
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}
```

### `sessao_chat.py`

```python
from pydantic import BaseModel, model_validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from agente_2w.enums.enums import EtapaFluxo, StatusSessao

class SessaoChatBase(BaseModel):
    canal: str
    contato_externo: str
    etapa_atual: EtapaFluxo
    status_sessao: StatusSessao
    cliente_id: Optional[UUID] = None
    codigo_motivo: Optional[str] = None
    mensagem_motivo: Optional[str] = None
    campo_relacionado: Optional[str] = None
    acao_bloqueada: Optional[str] = None

    @model_validator(mode="after")
    def bloqueio_exige_motivo(self):
        if self.status_sessao == StatusSessao.bloqueada:
            if not self.codigo_motivo or not self.mensagem_motivo:
                raise ValueError(
                    "sessao bloqueada exige codigo_motivo e mensagem_motivo"
                )
        return self

class SessaoChatCreate(SessaoChatBase):
    pass

class SessaoChat(SessaoChatBase):
    id: UUID
    ultima_interacao_em: datetime
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}
```

### `mensagem_chat.py`

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, Any
from agente_2w.enums.enums import Direcao, Remetente

class MensagemChatBase(BaseModel):
    sessao_chat_id: UUID
    direcao: Direcao
    remetente: Remetente
    conteudo_texto: str
    criado_em: datetime
    message_id_externo: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None

class MensagemChatCreate(MensagemChatBase):
    pass

class MensagemChat(MensagemChatBase):
    id: UUID
    registrado_em: datetime

    model_config = {"from_attributes": True}
```

### `contexto_conversa.py`

```python
from pydantic import BaseModel, model_validator
from datetime import datetime
from uuid import UUID
from typing import Optional, Any
from agente_2w.enums.enums import TipoDeVerdade, NivelConfirmacao, OrigemContexto

class ContextoConversaBase(BaseModel):
    sessao_chat_id: UUID
    chave: str
    tipo_de_verdade: TipoDeVerdade
    nivel_confirmacao: NivelConfirmacao
    fonte: OrigemContexto
    valor_texto: Optional[str] = None
    valor_json: Optional[Any] = None
    item_provisorio_id: Optional[UUID] = None
    mensagem_chat_id: Optional[UUID] = None
    referencia_fonte: Optional[str] = None
    observacao: Optional[str] = None
    ativo: bool = True

    @model_validator(mode="after")
    def valor_obrigatorio(self):
        if self.valor_texto is None and self.valor_json is None:
            raise ValueError("valor_texto ou valor_json deve existir")
        return self

    @model_validator(mode="after")
    def mensagem_cliente_exige_mensagem_id(self):
        if self.fonte == OrigemContexto.mensagem_cliente:
            if self.mensagem_chat_id is None:
                raise ValueError(
                    "fonte mensagem_cliente exige mensagem_chat_id"
                )
        return self

class ContextoConversaCreate(ContextoConversaBase):
    pass

class ContextoConversa(ContextoConversaBase):
    id: UUID
    coletado_em: datetime
    criado_em: datetime

    model_config = {"from_attributes": True}
```

### `item_provisorio.py`

```python
from pydantic import BaseModel, model_validator, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from decimal import Decimal
from agente_2w.enums.enums import StatusItemProvisorio, Posicao

class ItemProvisorioBase(BaseModel):
    sessao_chat_id: UUID
    status_item: StatusItemProvisorio
    pneu_id: Optional[UUID] = None
    posicao: Optional[Posicao] = None
    quantidade: int = 1
    preco_unitario_sugerido: Optional[Decimal] = None
    cliente_confirmou_em: Optional[datetime] = None
    validado_backend_em: Optional[datetime] = None
    observacao: Optional[str] = None

    @field_validator("quantidade")
    @classmethod
    def quantidade_minima(cls, v):
        if v < 1:
            raise ValueError("quantidade deve ser >= 1")
        return v

    @model_validator(mode="after")
    def promovido_exige_pneu(self):
        if self.status_item == StatusItemProvisorio.promovido:
            if self.pneu_id is None:
                raise ValueError("item promovido exige pneu_id")
        return self

class ItemProvisorioCreate(ItemProvisorioBase):
    pass

class ItemProvisorio(ItemProvisorioBase):

    id: UUID
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}
```

### `pneu.py`

```python
from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional

class PneuBase(BaseModel):
    marca: str
    modelo: str
    medida: str
    largura: int
    perfil: int
    aro: int
    descricao_comercial: str
    ativo: bool = True
    sku: Optional[str] = None
    tipo: Optional[str] = None

    @field_validator("largura")
    @classmethod
    def largura_positiva(cls, v):
        if v <= 0:
            raise ValueError("largura deve ser > 0")
        return v

    @field_validator("perfil")
    @classmethod
    def perfil_positivo(cls, v):
        if v <= 0:
            raise ValueError("perfil deve ser > 0")
        return v

    @field_validator("aro")
    @classmethod
    def aro_positivo(cls, v):
        if v <= 0:
            raise ValueError("aro deve ser > 0")
        return v

class Pneu(PneuBase):
    id: UUID
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}
```

### `moto.py`

```python
from pydantic import BaseModel, model_validator
from datetime import datetime
from uuid import UUID
from typing import Optional

class MotoBase(BaseModel):
    marca: str
    modelo: str
    descricao_resolvida: str
    versao: Optional[str] = None
    ano_inicio: Optional[int] = None
    ano_fim: Optional[int] = None

    @model_validator(mode="after")
    def intervalo_ano_valido(self):
        if self.ano_inicio and self.ano_fim:
            if self.ano_fim < self.ano_inicio:
                raise ValueError("ano_fim deve ser >= ano_inicio")
        return self

class Moto(MotoBase):
    id: UUID
    criado_em: datetime

    model_config = {"from_attributes": True}
```

### `medida_moto.py`

```python
from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID
from agente_2w.enums.enums import Posicao

class MedidaMotoBase(BaseModel):
    moto_id: UUID
    posicao: Posicao
    largura: int
    perfil: int
    aro: int
    fonte: str = "curadoria_2w"

    @field_validator("largura")
    @classmethod
    def largura_positiva(cls, v):
        if v <= 0:
            raise ValueError("largura deve ser > 0")
        return v

    @field_validator("perfil")
    @classmethod
    def perfil_positivo(cls, v):
        if v <= 0:
            raise ValueError("perfil deve ser > 0")
        return v

    @field_validator("aro")
    @classmethod
    def aro_positivo(cls, v):
        if v <= 0:
            raise ValueError("aro deve ser > 0")
        return v

class MedidaMotoCreate(MedidaMotoBase):
    pass

class MedidaMoto(MedidaMotoBase):
    id: UUID
    criado_em: datetime

    model_config = {"from_attributes": True}
```

### `estoque.py`

```python
from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from decimal import Decimal

class EstoqueBase(BaseModel):
    pneu_id: UUID
    quantidade_disponivel: int
    preco_venda: Decimal
    reservado: int = 0
    atualizado_por: Optional[str] = None

    @field_validator("quantidade_disponivel")
    @classmethod
    def quantidade_nao_negativa(cls, v):
        if v < 0:
            raise ValueError("quantidade_disponivel deve ser >= 0")
        return v

    @field_validator("preco_venda")
    @classmethod
    def preco_nao_negativo(cls, v):
        if v < 0:
            raise ValueError("preco_venda deve ser >= 0")
        return v

    @field_validator("reservado")
    @classmethod
    def reservado_nao_negativo(cls, v):
        if v < 0:
            raise ValueError("reservado deve ser >= 0")
        return v

class Estoque(EstoqueBase):
    id: UUID
    atualizado_em: datetime
    criado_em: datetime

    model_config = {"from_attributes": True}
```

### `pedido.py`

```python
from pydantic import BaseModel, model_validator, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional, Any
from decimal import Decimal
from agente_2w.enums.enums import TipoEntrega, FormaPagamento, StatusPedido

class PedidoBase(BaseModel):
    sessao_chat_id: UUID
    cliente_id: UUID
    tipo_entrega: TipoEntrega
    forma_pagamento: FormaPagamento
    valor_total: Decimal
    status_pedido: StatusPedido
    endereco_entrega_json: Optional[dict[str, Any]] = None

    @field_validator("tipo_entrega")
    @classmethod
    def tipo_entrega_fechado(cls, v):
        if v == TipoEntrega.a_confirmar:
            raise ValueError("pedido nao aceita tipo_entrega = a_confirmar")
        return v

    @field_validator("forma_pagamento")
    @classmethod
    def forma_pagamento_fechada(cls, v):
        if v == FormaPagamento.a_confirmar:
            raise ValueError("pedido nao aceita forma_pagamento = a_confirmar")
        return v

    @model_validator(mode="after")
    def entrega_exige_endereco(self):
        if self.tipo_entrega == TipoEntrega.entrega:
            if not self.endereco_entrega_json:
                raise ValueError(
                    "tipo_entrega = entrega exige endereco_entrega_json"
                )
        return self

class Pedido(PedidoBase):
    id: UUID
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}
```

### `item_pedido.py`

```python
from pydantic import BaseModel, model_validator, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from decimal import Decimal
from agente_2w.enums.enums import Posicao

class ItemPedidoBase(BaseModel):
    pedido_id: UUID
    pneu_id: UUID
    quantidade: int
    preco_unitario: Decimal
    subtotal: Decimal
    item_provisorio_id: Optional[UUID] = None
    posicao: Optional[Posicao] = None

    @field_validator("quantidade")
    @classmethod
    def quantidade_minima(cls, v):
        if v < 1:
            raise ValueError("quantidade deve ser >= 1")
        return v

    @model_validator(mode="after")
    def subtotal_coerente(self):
        esperado = self.quantidade * self.preco_unitario
        if self.subtotal != esperado:
            raise ValueError(
                f"subtotal ({self.subtotal}) deve ser quantidade * preco_unitario ({esperado})"
            )
        return self

class ItemPedido(ItemPedidoBase):
    id: UUID
    criado_em: datetime

    model_config = {"from_attributes": True}
```

### `endereco_entrega.py`

Schema Pydantic para o campo `pedido.endereco_entrega_json`. Obrigatorio antes de persistir.

```python
from pydantic import BaseModel
from typing import Optional

class EnderecoEntrega(BaseModel):
    logradouro: str
    numero: str
    bairro: str
    cidade: str
    estado: str
    cep: str
    complemento: Optional[str] = None
    referencia: Optional[str] = None
```

### `metadata_chat.py`

Schema Pydantic minimo para `mensagem_chat.metadata_json`. Validacao minima.

```python
from pydantic import BaseModel
from typing import Optional, Any

class MetadataChat(BaseModel):
    provider: str
    message_id_externo: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
```

## Schema do contexto executavel

Payload que o backend monta e entrega para a IA. Reflete o documento `contexto_executavel_agente.md`.

```python
# agente_2w/schemas/contexto_executavel.py

from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from agente_2w.enums.enums import (
    EtapaFluxo, StatusSessao, TipoDeVerdade,
    NivelConfirmacao, OrigemContexto, StatusItemProvisorio,
)

class SessaoContexto(BaseModel):
    sessao_id: str
    canal: str
    contato_externo: str
    etapa_atual: EtapaFluxo
    status_sessao: StatusSessao
    ultima_interacao_em: datetime

class ClienteContexto(BaseModel):
    cliente_id: Optional[str] = None
    nome: Optional[str] = None
    telefone: Optional[str] = None
    resolvido: bool = False

class BloqueioAtivo(BaseModel):
    codigo_motivo: str
    mensagem_motivo: str
    campo_relacionado: Optional[str] = None
    acao_bloqueada: str

class MensagemRecente(BaseModel):
    mensagem_id: str
    direcao: str
    remetente: str
    conteudo_texto: str
    criado_em: datetime

class FatoAtivo(BaseModel):
    chave: str
    valor: Any
    tipo_de_verdade: TipoDeVerdade
    nivel_confirmacao: NivelConfirmacao
    fonte: OrigemContexto
    mensagem_chat_id: Optional[str] = None
    item_provisorio_id: Optional[str] = None
    coletado_em: datetime

class ResultadoBusca(BaseModel):
    origem: str
    referencia_resultado: str
    pneu_id: Optional[str] = None
    descricao: str
    preco_venda: Optional[Decimal] = None
    quantidade_disponivel: Optional[int] = None
    compatibilidade_status: str
    observacao: Optional[str] = None

class ItemProvisorioContexto(BaseModel):
    item_provisorio_id: str
    pneu_id: Optional[str] = None
    descricao_contextual: str
    posicao: Optional[str] = None
    quantidade: int
    status_item: StatusItemProvisorio
    preco_unitario_sugerido: Optional[Decimal] = None
    cliente_confirmou: bool = False
    validado_backend: bool = False

class Pendencia(BaseModel):
    codigo: str
    descricao: str
    campo_relacionado: Optional[str] = None
    obrigatoria_para: str

class ResumoOperacional(BaseModel):
    tem_item_validado: bool = False
    tem_entrega_definida: bool = False
    tem_pagamento_definido: bool = False
    pode_avancar_etapa: bool = False

class Metadados(BaseModel):
    gerado_em: datetime
    versao_contexto: str = "v1"

class ContextoExecutavel(BaseModel):
    sessao: SessaoContexto
    cliente: ClienteContexto
    bloqueios_ativos: list[BloqueioAtivo] = Field(default_factory=list)
    mensagens_recentes: list[MensagemRecente] = Field(default_factory=list)
    fatos_ativos: list[FatoAtivo] = Field(default_factory=list)
    resultados_busca_atuais: list[ResultadoBusca] = Field(default_factory=list)
    itens_provisorios: list[ItemProvisorioContexto] = Field(default_factory=list)
    pendencias: list[Pendencia] = Field(default_factory=list)
    acoes_permitidas: list[str] = Field(default_factory=list)
    resumo_operacional: ResumoOperacional = Field(default_factory=ResumoOperacional)
    metadados: Metadados
```

## Schema do envelope da IA

Resposta estruturada que a IA retorna ao backend para validacao.

```python
# agente_2w/schemas/envelope_ia.py

from pydantic import BaseModel, Field
from typing import Optional, Any
from agente_2w.enums.enums import EtapaFluxo, Confianca

class FatoObservado(BaseModel):
    chave: str
    valor: Any
    mensagem_chat_id: Optional[str] = None

class FatoInferido(BaseModel):
    chave: str
    valor: Any
    justificativa: str

class MudancaContexto(BaseModel):
    chave: str
    valor_novo: Any
    motivo: str

class MudancaItem(BaseModel):
    item_provisorio_id: Optional[str] = None
    acao: str
    dados: Optional[dict[str, Any]] = None

class BloqueioIdentificado(BaseModel):
    codigo_motivo: str
    mensagem_motivo: str
    campo_relacionado: Optional[str] = None

class EnvelopeIA(BaseModel):
    mensagem_cliente: str
    etapa_atual: EtapaFluxo
    intencao_atual: str
    acoes_sugeridas: list[str]
    pendencias: list[str] = Field(default_factory=list)
    confianca: Confianca
    fatos_observados: list[FatoObservado] = Field(default_factory=list)
    fatos_inferidos: list[FatoInferido] = Field(default_factory=list)
    mudancas_contexto: list[MudancaContexto] = Field(default_factory=list)
    mudancas_itens: list[MudancaItem] = Field(default_factory=list)
    bloqueios_identificados: list[BloqueioIdentificado] = Field(default_factory=list)
```

## Maquina de estados

Define transicoes permitidas e bloqueios.

```python
# agente_2w/engine/maquina_estados.py

from agente_2w.enums.enums import EtapaFluxo

TRANSICOES_PERMITIDAS: dict[EtapaFluxo, list[EtapaFluxo]] = {
    EtapaFluxo.identificacao: [
        EtapaFluxo.busca,
    ],
    EtapaFluxo.busca: [
        EtapaFluxo.oferta,
        EtapaFluxo.identificacao,  # retorno por ambiguidade
    ],
    EtapaFluxo.oferta: [
        EtapaFluxo.confirmacao_item,
        EtapaFluxo.busca,  # retorno por mudanca de criterio
    ],
    EtapaFluxo.confirmacao_item: [
        EtapaFluxo.entrega_pagamento,
        EtapaFluxo.oferta,  # retorno por rejeicao
    ],
    EtapaFluxo.entrega_pagamento: [
        EtapaFluxo.fechamento,
        EtapaFluxo.confirmacao_item,  # retorno por mudanca
    ],
    EtapaFluxo.fechamento: [],  # estado terminal
}

def transicao_permitida(atual: EtapaFluxo, destino: EtapaFluxo) -> bool:
    return destino in TRANSICOES_PERMITIDAS.get(atual, [])

def motivo_bloqueio(atual: EtapaFluxo, destino: EtapaFluxo) -> str:
    return (
        f"transicao de {atual.value} para {destino.value} nao e permitida "
        f"no fluxo V1"
    )
```

## Acoes permitidas por etapa

Lista fechada que o backend calcula para limitar a IA.

```python
# agente_2w/engine/pendencias.py

from agente_2w.enums.enums import EtapaFluxo

ACOES_POR_ETAPA: dict[EtapaFluxo, list[str]] = {
    EtapaFluxo.identificacao: [
        "pedir_clarificacao_moto",
        "pedir_clarificacao_medida",
        "pedir_clarificacao_posicao",
        "buscar_por_moto",
        "buscar_por_medida",
        "registrar_fato_observado",
        "responder_incerteza_segura",
    ],
    EtapaFluxo.busca: [
        "buscar_por_moto",
        "buscar_por_medida",
        "buscar_medida_proxima",
        "pedir_clarificacao_moto",
        "pedir_clarificacao_medida",
        "registrar_opcoes_encontradas",
        "responder_incerteza_segura",
    ],
    EtapaFluxo.oferta: [
        "apresentar_opcoes",
        "explicar_falta",
        "pedir_escolha_cliente",
        "responder_incerteza_segura",
    ],
    EtapaFluxo.confirmacao_item: [
        "confirmar_item",
        "registrar_quantidade",
        "registrar_posicao",
        "rejeitar_item",
        "responder_incerteza_segura",
    ],
    EtapaFluxo.entrega_pagamento: [
        "perguntar_tipo_entrega",
        "perguntar_endereco",
        "perguntar_forma_pagamento",
        "registrar_entrega",
        "registrar_pagamento",
        "responder_incerteza_segura",
    ],
    EtapaFluxo.fechamento: [
        "revisar_pedido",
        "converter_em_pedido",
        "responder_incerteza_segura",
    ],
}

def acoes_permitidas(etapa: EtapaFluxo) -> list[str]:
    return ACOES_POR_ETAPA.get(etapa, ["responder_incerteza_segura"])
```

## Montador do contexto executavel

Funcao principal que consulta o banco e monta o payload para a IA.

```python
# agente_2w/engine/montador_contexto.py (estrutura)

async def montar_contexto(sessao_id: str) -> ContextoExecutavel:
    """
    1. buscar sessao_chat por id
    2. buscar cliente se sessao.cliente_id existir
    3. buscar mensagens recentes (janela limitada, ex: ultimas 20)
    4. buscar fatos ativos (contexto_conversa WHERE ativo = true)
    5. buscar itens provisorios da sessao
    6. calcular bloqueios ativos a partir da sessao
    7. calcular pendencias a partir da etapa atual e fatos faltantes
    8. calcular acoes permitidas a partir da etapa atual
    9. calcular resumo operacional
    10. montar e retornar ContextoExecutavel
    """
    pass
```

## Orquestrador — loop de um turno

Passo a passo de um turno completo do agente.

```python
# agente_2w/engine/orquestrador.py (estrutura)

async def processar_turno(sessao_id: str, mensagem_texto: str) -> str:
    """
    1. persistir mensagem de entrada em mensagem_chat
    2. montar contexto executavel do turno
    3. enviar contexto + mensagem para a IA
    4. receber envelope estruturado da IA
    5. validar envelope (acoes dentro do permitido, sem ids inventados)
    6. aplicar mudancas de contexto propostas pela IA:
       a. registrar fatos observados em contexto_conversa
       b. registrar fatos inferidos em contexto_conversa (como inferido)
       c. aplicar mudancas em itens provisorios
    7. avaliar se a etapa deve mudar:
       a. verificar se a transicao e permitida
       b. se sim, atualizar sessao_chat.etapa_atual
       c. se nao, registrar bloqueio
    8. persistir mensagem de saida em mensagem_chat
    9. retornar mensagem_cliente do envelope como resposta
    """
    pass
```

## Validador do envelope

Verifica se a resposta da IA esta dentro do contrato.

```python
# agente_2w/engine/validador_envelope.py (regras)

def validar_envelope(envelope: EnvelopeIA, contexto: ContextoExecutavel) -> list[str]:
    """
    Retorna lista de erros. Lista vazia = envelope valido.

    Validacoes:
    1. acoes_sugeridas devem estar dentro de acoes_permitidas do contexto
    2. etapa_atual do envelope deve ser igual ou transicao valida da etapa do contexto
    3. fatos_observados nao devem conter ids inventados
    4. fatos_inferidos devem estar marcados como inferidos (nao como validados)
    5. mudancas_itens nao devem promover item sem validacao
    6. confianca deve ser enum valido
    """
    pass
```

## Promotor — item provisorio para item oficial

So roda no fechamento, apos validacao completa.

```python
# agente_2w/engine/promotor.py (estrutura)

async def promover_para_pedido(sessao_id: str) -> Pedido:
    """
    Pre-condicoes (todas obrigatorias):
    1. sessao.etapa_atual == fechamento
    2. sessao.cliente_id existe (cliente resolvido)
    3. pelo menos um item_provisorio com status = validado e pneu_id
    4. tipo_entrega definido e != a_confirmar
    5. forma_pagamento definida e != a_confirmar
    6. se tipo_entrega = entrega, endereco_entrega_json deve existir
    7. estoque suficiente para cada item

    Processo:
    1. criar pedido
    2. para cada item_provisorio validado:
       a. criar item_pedido com preco e quantidade congelados
       b. atualizar item_provisorio.status_item = promovido
    3. atualizar sessao.status_sessao = fechada
    4. retornar pedido criado
    """
    pass
```

## Tools de leitura

### `busca_catalogo.py`

```python
async def buscar_por_medida(medida: str) -> list[ResultadoBusca]:
    """
    Busca pneus ativos com a medida informada.
    Retorna com preco e estoque.
    Compatibilidade marcada como nao_validada.
    """
    pass

async def buscar_por_moto(marca: str, modelo: str) -> list[ResultadoBusca]:
    """
    Busca pneus associados a uma moto.
    No V1 sem tabela de compatibilidade, retorna por medidas conhecidas.
    Compatibilidade marcada como nao_validada.
    """
    pass
```

### `consulta_estoque.py`

```python
async def consultar_disponibilidade(pneu_id: str) -> Optional[Estoque]:
    """
    Retorna estoque atual do pneu.
    Nao afirma disponibilidade se nao encontrar registro.
    """
    pass
```

### `resolve_cliente.py`

```python
async def resolver_cliente(telefone: str) -> Cliente:
    """
    Busca cliente por telefone.
    Se nao existir, cria com dados minimos.
    Retorna cliente resolvido.
    """
    pass
```

## Integracao com a IA

### System prompt

```python
# agente_2w/ia/prompt_sistema.py

SYSTEM_PROMPT = """
Voce e o agente comercial da 2W Pneus, especialista em pneus de moto.

Regras absolutas:
- voce nunca inventa pneu_id, preco, estoque ou compatibilidade
- voce nunca afirma compatibilidade sem validacao de tool ou backend
- voce nunca pula etapas do fluxo
- voce sempre responde em portugues brasileiro, de forma natural e comercial
- voce sempre respeita a etapa atual e as acoes permitidas
- quando nao tiver certeza, pergunte ou declare incerteza

Voce recebe um contexto executavel em JSON com:
- sessao (etapa atual, status)
- cliente (resolvido ou nao)
- fatos ativos (com evidencia)
- resultados de busca (opcoes do turno)
- itens provisorios (em discussao)
- pendencias (o que falta)
- acoes permitidas (o que voce pode fazer)

Voce deve retornar um envelope JSON estruturado com:
- mensagem_cliente: resposta para o cliente
- etapa_atual: etapa vigente
- intencao_atual: o que o cliente quer
- acoes_sugeridas: lista de acoes que voce propoe
- pendencias: lista do que falta
- confianca: alta, media ou baixa
- fatos_observados: fatos que voce identificou na mensagem
- fatos_inferidos: deducoes que precisam de validacao
- mudancas_contexto: propostas de alteracao
- mudancas_itens: propostas para itens provisorios
- bloqueios_identificados: problemas que impedem avanco
"""
```

### Chamada ao Claude

```python
# agente_2w/ia/agente.py (estrutura)

async def chamar_ia(
    contexto: ContextoExecutavel,
    mensagem_cliente: str,
) -> EnvelopeIA:
    """
    1. serializar contexto executavel para JSON
    2. montar mensagem com system prompt + contexto + mensagem do cliente
    3. chamar Claude via Anthropic SDK com tool_use ou structured output
    4. parsear resposta em EnvelopeIA
    5. retornar envelope
    """
    pass
```

## Ordem de implementacao com dependencias

Cada passo depende dos anteriores. Nao pular.

### Fase 1 — Fundacao (sem IA)

| Passo | Arquivo | Depende de | Descricao |
|---:|---|---|---|
| 1 | `config.py` | nada | variaveis de ambiente, chaves |
| 2 | `enums/enums.py` | nada | todos os enums |
| 3 | `db/client.py` | config | cliente Supabase inicializado |
| 4 | `schemas/*.py` (entidades) | enums | schemas de todas as tabelas |
| 5 | `schemas/endereco_entrega.py` | nada | schema do jsonb de endereco |
| 6 | `schemas/metadata_chat.py` | nada | schema do jsonb de metadata |

### Fase 2 — Repositorios (acesso ao banco)

| Passo | Arquivo | Depende de | Descricao |
|---:|---|---|---|
| 7 | `db/sessao_repo.py` | client, schemas | CRUD de sessao_chat |
| 8 | `db/mensagem_repo.py` | client, schemas | CRUD de mensagem_chat |
| 9 | `db/contexto_repo.py` | client, schemas | CRUD de contexto_conversa |
| 10 | `db/item_provisorio_repo.py` | client, schemas | CRUD de item_provisorio |
| 11 | `db/cliente_repo.py` | client, schemas | CRUD de cliente |
| 12 | `db/catalogo_repo.py` | client, schemas | leitura de pneu + estoque + moto |
| 13 | `db/pedido_repo.py` | client, schemas | criacao de pedido + item_pedido |

### Fase 3 — Engine (logica de negocio)

| Passo | Arquivo | Depende de | Descricao |
|---:|---|---|---|
| 14 | `engine/maquina_estados.py` | enums | transicoes e bloqueios |
| 15 | `engine/pendencias.py` | enums | acoes permitidas por etapa |
| 16 | `engine/montador_contexto.py` | repos, schemas | monta payload para a IA |
| 17 | `engine/validador_envelope.py` | schemas | valida resposta da IA |
| 18 | `engine/promotor.py` | repos, schemas | converte em pedido |

### Fase 4 — Tools (leitura operacional)

| Passo | Arquivo | Depende de | Descricao |
|---:|---|---|---|
| 19 | `tools/busca_catalogo.py` | catalogo_repo | busca por medida e moto |
| 20 | `tools/consulta_estoque.py` | catalogo_repo | verifica disponibilidade |
| 21 | `tools/resolve_cliente.py` | cliente_repo | resolve ou cria cliente |

### Fase 5 — IA (integracao)

| Passo | Arquivo | Depende de | Descricao |
|---:|---|---|---|
| 22 | `schemas/contexto_executavel.py` | enums | payload para a IA |
| 23 | `schemas/envelope_ia.py` | enums | resposta da IA |
| 24 | `ia/prompt_sistema.py` | nada | system prompt |
| 25 | `ia/agente.py` | contexto_executavel, envelope_ia | chamada ao Claude |
| 26 | `ia/parser_envelope.py` | envelope_ia | parse da resposta |

### Fase 6 — Orquestrador (tudo junto)

| Passo | Arquivo | Depende de | Descricao |
|---:|---|---|---|
| 27 | `engine/orquestrador.py` | tudo acima | loop completo de um turno |
| 28 | `main.py` | orquestrador | ponto de entrada para testes |

## Criterio de pronto por fase

### Fase 1 — Fundacao
- [ ] enums importaveis e testados
- [ ] schemas instanciaveis com dados validos
- [ ] schemas rejeitam dados invalidos (bloqueio sem motivo, subtotal errado, etc)
- [ ] cliente Supabase conecta e executa query simples

### Fase 2 — Repositorios
- [ ] cada repo consegue criar e ler registros no banco real
- [ ] fatos ativos sao filtrados corretamente
- [ ] desativar fato antigo ao inserir novo funciona

### Fase 3 — Engine
- [ ] maquina de estados bloqueia transicoes invalidas
- [ ] montador_contexto retorna ContextoExecutavel valido
- [ ] validador_envelope rejeita acoes fora do permitido
- [ ] promotor cria pedido apenas com pre-condicoes atendidas

### Fase 4 — Tools
- [ ] busca por medida retorna pneus reais do banco
- [ ] consulta estoque retorna dados reais
- [ ] resolve_cliente cria ou encontra cliente

### Fase 5 — IA
- [ ] chamada ao Claude retorna envelope parseavel
- [ ] envelope invalido e rejeitado antes de aplicar mudancas

### Fase 6 — Orquestrador
- [ ] turno completo funciona: mensagem entra, contexto monta, IA responde, mudancas aplicam, resposta sai
- [ ] conversa nao vira pedido sem validacao completa
