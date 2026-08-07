import json
import logging
import uuid
from pydantic import ValidationError as PydanticValidationError
from domain.event_schema import OrderPlacedEventDetail
from shared.error_handler import ErrorClassifier, ValidationError as DomainValidationError
from shared.event_publisher import EventPublisher
from shared.response_utils import create_success_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicialização global para reaproveitamento em Warm Starts
event_publisher = EventPublisher()


def handler(event: dict, context: any) -> dict:
    """
    Handler da AWS Lambda responsável pelo Checkout/Compra de Pedidos (POST /orders).

    Fluxo:
      1. Valida a payload da ordem com Pydantic v2.
      2. Gera o order_id único (UUID v4).
      3. Publica o evento 'Order Placed' no Amazon EventBridge (Desacoplado).
      4. Retorna HTTP 201 Created imediatamente para o cliente.
    """
    logger.info(f"Iniciando checkout do pedido. Evento: {json.dumps(event)}")
    request_id = context.aws_request_id if context else "fallback-local-id"

    try:
        body_str = event.get("body")
        if not body_str:
            raise DomainValidationError("O corpo da requisição de compra (body) está vazio ou ausente.")

        body_json = json.loads(body_str)

        # Se o order_id não for enviado pelo cliente, gera um UUID v4 automaticamente
        if "order_id" not in body_json:
            body_json["order_id"] = f"ord_{str(uuid.uuid4())[:8]}"

        # Validação do evento de pedido com Pydantic v2
        validated_order = OrderPlacedEventDetail.model_validate(body_json)
        order_data = validated_order.model_dump()

        # Publica o evento no Amazon EventBridge (Roteia para SQS -> Worker -> SNS e Firehose)
        event_publisher.publish_order_placed(order_data)

        logger.info(f"Pedido #{validated_order.order_id} criado e enviado para o barramento com sucesso!")
        return create_success_response(201, {
            "message": "Pedido recebido com sucesso e enviado para processamento.",
            "order_id": validated_order.order_id,
            "customer_id": validated_order.customer_id,
            "total_amount": validated_order.total_amount,
            "status": "PROCESSING"
        })

    except PydanticValidationError as e:
        logger.warning(f"Falha na validação do pedido (Pydantic): {e.errors()}")
        return ErrorClassifier.handle_exception(e, request_id)

    except json.JSONDecodeError:
        logger.warning("Sintaxe JSON inválida na requisição de compra.")
        custom_error = DomainValidationError("Formato JSON inválido no corpo do pedido.")
        return ErrorClassifier.handle_exception(custom_error, request_id)

    except DomainValidationError as e:
        logger.warning(f"Erro de validação de negócio no pedido: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)

    except Exception as e:
        logger.exception("Erro inesperado durante o checkout do pedido.")
        return ErrorClassifier.handle_exception(e, request_id)