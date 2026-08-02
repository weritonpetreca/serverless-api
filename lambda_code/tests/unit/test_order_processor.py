import json
import pytest
from handlers.order_processor import handler
from shared.error_handler import OrderProcessingException


@pytest.fixture
def sample_sqs_event():
    """Gera um evento fictício do SQS contendo uma mensagem do EventBridge."""
    order_detail = {
        "order_id": "ord_12345678_uuid",
        "customer_id": "cust_999",
        "customer_email": "cliente@email.com",
        "customer_tier": "vip",
        "order_type": "express",
        "total_amount": 499.90,
        "items": [
            {"product_id": "prod_1", "quantity": 1, "price": 499.90}
        ]
    }

    eventbridge_payload = {
        "source": "store.orders",
        "detail-type": "Order Placed",
        "detail": order_detail
    }

    return {
        "Records": [
            {
                "messageId": "msg_001",
                "receiptHandle": "handle_001",
                "body": json.dumps(eventbridge_payload)
            }
        ]
    }


def test_order_processor_success(sample_sqs_event, mocker):
    """Cenário 1: Sucesso completo nas 3 etapas + notificação SNS."""
    mocker.patch("handlers.order_processor.sns_client.publish", return_value={"MessageId": "sns_msg_123"})
    mocker.patch("handlers.order_processor.repository.get_by_id", return_value={"id": "prod_1", "title": "Teclado RGB"})

    mock_ssm = mocker.patch("handlers.order_processor.config_manager")
    mock_ssm.is_feature_enabled.return_value = True

    response = handler(sample_sqs_event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["processed_count"] == 1


def test_order_processor_disabled_by_feature_flag(sample_sqs_event, mocker):
    """Cenário 2: Suspensão de pedidos via SSM Feature Flag."""
    mock_ssm = mocker.patch("handlers.order_processor.config_manager")
    mock_ssm.is_feature_enabled.return_value = False

    response = handler(sample_sqs_event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "suspenso" in body["message"]


def test_order_processor_triggers_rollback_when_product_not_found(sample_sqs_event, mocker):
    """Cenário 3: Produto não encontrado no DynamoDB dispara estorno compensatório."""
    mocker.patch("handlers.order_processor.repository.get_by_id", return_value=None)

    mock_ssm = mocker.patch("handlers.order_processor.config_manager")
    mock_ssm.is_feature_enabled.return_value = True

    mock_rollback = mocker.patch("handlers.order_processor._rollback_completed_steps")

    with pytest.raises(OrderProcessingException):
        handler(sample_sqs_event, None)

    mock_rollback.assert_called_once()


def test_order_processor_triggers_rollback_when_payment_fails(sample_sqs_event, mocker):
    """Cenário 4: Falha no pagamento após validação de estoque libera a reserva."""
    mocker.patch("handlers.order_processor.repository.get_by_id", return_value={"id": "prod_1", "title": "Teclado RGB"})
    mocker.patch("handlers.order_processor._process_payment_step", side_effect=RuntimeError("Cartão recusado"))

    mock_ssm = mocker.patch("handlers.order_processor.config_manager")
    mock_ssm.is_feature_enabled.return_value = True

    mock_rollback = mocker.patch("handlers.order_processor._rollback_completed_steps")

    with pytest.raises(OrderProcessingException):
        handler(sample_sqs_event, None)

    mock_rollback.assert_called_once()


def test_order_processor_handles_malformed_json_payload(mocker):
    """Cenário 5: Payload SQS com JSON malformado lança exceção para acionar DLQ."""
    malformed_event = {
        "Records": [
            {
                "messageId": "msg_bad",
                "body": "JSON_INVALIDO_SINTAXE"
            }
        ]
    }

    mock_ssm = mocker.patch("handlers.order_processor.config_manager")
    mock_ssm.is_feature_enabled.return_value = True

    with pytest.raises(OrderProcessingException):
        handler(malformed_event, None)


def test_order_processor_handles_sns_publish_error_gracefully(sample_sqs_event, mocker):
    """Cenário 6: Falha no SNS registra log de exceção sem derrubar o pedido se concluído."""
    mocker.patch("handlers.order_processor.sns_client.publish", side_effect=RuntimeError("SNS throttled"))
    mocker.patch("handlers.order_processor.repository.get_by_id", return_value={"id": "prod_1", "title": "Teclado RGB"})

    mock_ssm = mocker.patch("handlers.order_processor.config_manager")
    mock_ssm.is_feature_enabled.return_value = True

    response = handler(sample_sqs_event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["processed_count"] == 1