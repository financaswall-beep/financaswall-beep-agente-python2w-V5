from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class EscalacaoCreate(BaseModel):
    sessao_chat_id: UUID
    chatwoot_conv_id: int
    motivo: str
    origem: str
    chatwoot_team_id: Optional[int] = None


class Escalacao(EscalacaoCreate):
    id: UUID
    status: str = "aguardando"
    notas: Optional[str] = None
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}
