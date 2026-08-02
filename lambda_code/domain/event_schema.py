from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timezone


class OrderItemPayload(BaseModel):
    """Schema para cada item do pedido dentro da payload do evento."""
    product_id: str = Field(description="ID único do produto no DynamoDB")
    quantity: int = Field(gt=0, description="Quantidade do item (deve ser maior que zero)")
    price: float = Field(gt=0.0, description="Preço unitário em Reais")


class OrderPlacedEventDetail(BaseModel):
    """
    Schema do detalhe do evento 'Order Placed' (Event-Carried State Transfer).
    Carrega a carga de dados necessária para que os consumidores processem
    o pedido de forma autônoma.
    """
    order_id: str = Field(description="ID único do pedido (UUID v4)")
    customer_id: str = Field(description="ID único do cliente")
    customer_email: str = Field(description="E-mail de contato do cliente")
    customer_tier: str = Field(default="regular", description="Categoria do cliente: regular, premium, vip")
    order_type: str = Field(default="standard", description="Tipo de frete: standard, express")
    total_amount: float = Field(gt=0.0, description="Valor total do pedido em Reais")
    items: List[OrderItemPayload] = Field(min_length=1, description="Lista contendo ao menos 1 item do pedido")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        description="Carimbo de data/hora ISO 8601 UTC"
    )


class EventBridgeEnvelope(BaseModel):
    """Envelope padronizado do Amazon EventBridge para publicação."""
    source: str = Field(default="store.orders", description="Origem do evento")
    detail_type: str = Field(default="Order Placed", description="Tipo de evento de negócio")
    detail: OrderPlacedEventDetail
    event_bus_name: str = Field(default="online-store-events", description="Nome do barramento customizado")