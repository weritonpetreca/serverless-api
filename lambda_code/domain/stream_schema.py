from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class CustomerActivityRecord(BaseModel):
    """
    Schema Pydantic v2 para validação e enriquecimento de eventos de streaming
    ingeridos pelo Amazon Data Firehose.
    """
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        description="Carimbo de data/hora ISO 8601 UTC"
    )
    event_type: str = Field(description="Tipo de evento: product_view, cart_add, search, purchase")
    user_id: str = Field(description="ID do usuário ou cliente")
    session_id: str = Field(default="session_unknown", description="ID da sessão do navegador")
    product_id: Optional[str] = Field(default=None, description="ID do produto associado (se aplicável)")
    product_name: Optional[str] = Field(default=None, description="Nome enriquecido do produto no DynamoDB")
    category: Optional[str] = Field(default=None, description="Categoria enriquecida do produto")
    price: Optional[float] = Field(default=None, description="Preço enriquecido do produto em Reais")