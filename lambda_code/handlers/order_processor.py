import json
import logging
import os
from typing import Dict, Any, List
import boto3

from domain.event_schema import OrderPlacedEventDetail
from repository.products_db import ProductsRepository
from shared.config_manager import SSMParameterManager
from shared.error_handler import OrderProcessingException, ProductNotFoundError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicialização global de clientes Boto3 e Gerenciadores (Warm Starts)
sns_client = boto3.client("sns")
repository = ProductsRepository()
config_manager = SSMParameterManager(ttl_seconds=300)


def _validate_and_reserve_inventory_step(order_data: OrderPlacedEventDetail) -> Dict[str, Any]:
    """
    Etapa 1 REAL: Consulta a existência de cada produto no DynamoDB via ProductsRepository.
    """
    logger.info(f"[Passo 1/3] Validando catálogo/estoque no DynamoDB para o pedido {order_data.order_id}")

    for item in order_data.items:
        product = repository.get_by_id(item.product_id)
        if not product:
            logger.warning(f"Produto ID '{item.product_id}' não localizado no DynamoDB.")
            raise ProductNotFoundError(f"Item {item.product_id} não encontrado para reserva de estoque.")

    return {"success": True, "validated_items_count": len(order_data.items)}


def _process_payment_step(order_data: OrderPlacedEventDetail) -> Dict[str, Any]:
    """Etapa 2: Processamento de cobrança do pedido."""
    logger.info(f"[Passo 2/3] Efetuando cobrança de R$ {order_data.total_amount:.2f} para o pedido {order_data.order_id}")
    return {"success": True, "transaction_id": f"tx_{order_data.order_id[:8]}"}


def _create_shipping_label_step(order_data: OrderPlacedEventDetail) -> Dict[str, Any]:
    """Etapa 3: Emissão de etiqueta de envio."""
    logger.info(f"[Passo 3/3] Emitindo etiqueta de envio tipo '{order_data.order_type}' para o pedido {order_data.order_id}")
    return {"success": True, "tracking_code": f"BR{order_data.order_id[:8]}TRACK"}


def _rollback_completed_steps(completed_steps: List[Dict[str, Any]], order_id: str) -> None:
    """
    Padrão de Transação Compensatória (Saga Pattern):
    Executa estornos das etapas já concluídas em ordem reversa caso ocorra uma falha.
    """
    logger.warning(f"Iniciando estorno compensatório para {len(completed_steps)} etapa(s) do pedido: {order_id}")

    for step in reversed(completed_steps):
        step_name = step.get("step")
        try:
            if step_name == "process_payment":
                tx_id = step.get("result", {}).get("transaction_id")
                logger.info(f"[ROLLBACK] Estornando cobrança de pagamento ID: {tx_id}")
            elif step_name == "validate_inventory":
                logger.info(f"[ROLLBACK] Liberando reserva de estoque para o pedido: {order_id}")
        except Exception:
            logger.exception(f"Falha ao executar estorno da etapa {step_name}.")


def _publish_sns_confirmation(order_data: OrderPlacedEventDetail, topic_arn: str) -> None:
    """Dispara notificação multicanal ao cliente via Amazon SNS."""
    if not topic_arn:
        logger.warning("CUSTOMER_NOTIFICATION_TOPIC não configurado nas variáveis de ambiente. Pulando SNS.")
        return

    try:
        message_body = {
            "default": f"Pedido #{order_data.order_id[:8]} confirmado! Total: R$ {order_data.total_amount:.2f}",
            "email": (
                f"Olá! Seu pedido #{order_data.order_id} foi confirmado com sucesso.\n\n"
                f"Valor Total: R$ {order_data.total_amount:.2f}\n"
                f"Tipo de Frete: {order_data.order_type}\n"
                f"Obrigado por comprar em nossa loja!"
            )
        }

        message_attributes = {
            "customer_tier": {
                "DataType": "String",
                "StringValue": order_data.customer_tier
            },
            "order_type": {
                "DataType": "String",
                "StringValue": order_data.order_type
            }
        }

        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message_body),
            MessageStructure="json",
            Subject=f"Confirmação do Pedido #{order_data.order_id[:8]}",
            MessageAttributes=message_attributes
        )
        logger.info(f"Notificação SNS disparada com sucesso para o tópico: {topic_arn}")

    except Exception:
        logger.exception("Erro ao disparar notificação multicanal via Amazon SNS.")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler da AWS Lambda Worker acionada por lotes de mensagens do Amazon SQS.
    """
    logger.info(f"Iniciando processamento de lote SQS. Total de registros: {len(event.get('Records', []))}")
    records = event.get("Records", [])
    topic_arn = os.environ.get("CUSTOMER_NOTIFICATION_TOPIC", "")

    # Checagem da Feature Flag ESPECÍFICA de Pedidos no SSM
    if not config_manager.is_feature_enabled("feature_flag_order_processing"):
        logger.warning("Processamento de pedidos suspenso temporariamente via SSM Feature Flag.")
        return {"statusCode": 200, "body": json.dumps({"message": "Processamento de pedidos suspenso via Feature Flag."})}

    processed_count = 0

    for record in records:
        message_body_raw = record.get("body", "{}")
        completed_steps = []
        current_order_id = "desconhecido"

        try:
            sqs_payload = json.loads(message_body_raw)
            event_detail_raw = sqs_payload.get("detail", sqs_payload)
            order_data = OrderPlacedEventDetail.model_validate(event_detail_raw)
            current_order_id = order_data.order_id

            logger.info(f"Processando pedido ID: {current_order_id} (Cliente: {order_data.customer_id})")

            # 1. Validação Real no DynamoDB
            inv_res = _validate_and_reserve_inventory_step(order_data)
            completed_steps.append({"step": "validate_inventory", "result": inv_res})

            # 2. Pagamento
            pay_res = _process_payment_step(order_data)
            completed_steps.append({"step": "process_payment", "result": pay_res})

            # 3. Envio
            ship_res = _create_shipping_label_step(order_data)
            completed_steps.append({"step": "create_shipping", "result": ship_res})

            # 4. Notificação SNS
            _publish_sns_confirmation(order_data, topic_arn)

            processed_count += 1
            logger.info(f"Pedido {current_order_id} processado com sucesso!")

        except Exception:
            logger.exception(f"Erro catastrófico ao processar pedido ID '{current_order_id}' no SQS. Executando estorno compensatório.")
            _rollback_completed_steps(completed_steps, current_order_id)
            raise OrderProcessingException(f"Falha de processamento no pedido {current_order_id}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Processamento de lote SQS concluído.",
            "processed_count": processed_count
        })
    }