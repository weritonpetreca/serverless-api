import json
import logging
import os
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from domain.event_schema import OrderPlacedEventDetail, EventBridgeEnvelope
from shared.error_handler import EventPublishError, RetryableError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Boto3 client inicializado no escopo global para reaproveitamento em Warm Starts
_eventbridge_client = None


def _get_eventbridge_client():
    global _eventbridge_client
    if _eventbridge_client is None:
        _eventbridge_client = boto3.client("events")
    return _eventbridge_client


class EventPublisher:
    """
    Utilitário para validação e publicação de eventos de negócio no Amazon EventBridge.
    Garante o desacoplamento da API Gateway em relação aos consumidores de segundo plano.
    """

    def __init__(self, event_bus_name: Optional[str] = None) -> None:
        self.event_bus_name = event_bus_name or os.environ.get("EVENT_BUS_NAME", "online-store-events")

    def publish_order_placed(self, order_detail_data: Dict[str, Any]) -> str:
        """
        Valida a payload contra o schema Pydantic v2 e publica o evento 'Order Placed' no EventBridge.
        Retorna o event_id gerado pela AWS em caso de sucesso.
        """
        try:
            # 1. Validação Shift-Left do evento com Pydantic v2
            validated_detail = OrderPlacedEventDetail.model_validate(order_detail_data)

            envelope = EventBridgeEnvelope(
                source="store.orders",
                detail_type="Order Placed",
                detail=validated_detail,
                event_bus_name=self.event_bus_name
            )

            # 2. Formatação para a API do Boto3 PutEvents
            event_entry = {
                "Source": envelope.source,
                "DetailType": envelope.detail_type,
                "Detail": json.dumps(envelope.detail.model_dump()),
                "EventBusName": self.event_bus_name
            }

            logger.info(
                f"Publicando evento '{envelope.detail_type}' para o pedido ID: {validated_detail.order_id} "
                f"no EventBus '{self.event_bus_name}'"
            )

            client = _get_eventbridge_client()
            response = client.put_events(Entries=[event_entry])

            # 3. Verificação de FailedEntryCount
            failed_count = response.get("FailedEntryCount", 0)
            if failed_count > 0:
                error_entry = response.get("Entries", [{}])[0]
                error_code = error_entry.get("ErrorCode", "UnknownError")
                error_msg = error_entry.get("ErrorMessage", "Falha na ingestão do EventBridge")

                logger.exception("Falha na ingestão de evento no Amazon EventBridge.")
                raise EventPublishError(f"Erro ao publicar evento no EventBridge ({error_code}): {error_msg}")

            event_id = response.get("Entries", [{}])[0].get("EventId", "unknown-event-id")
            logger.info(f"Evento publicado com sucesso no EventBridge! EventID: {event_id}")
            return event_id

        except ClientError as e:
            logger.exception("Erro no SDK Boto3 ao comunicar com o Amazon EventBridge.")
            raise RetryableError(f"Instabilidade de comunicação com o EventBridge: {str(e)}")

        except Exception:
            logger.exception("Erro inesperado durante a publicação do evento no EventBridge.")
            raise