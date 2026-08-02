import pytest
from pydantic import ValidationError
from shared.event_publisher import EventPublisher
from shared.error_handler import EventPublishError
from unittest.mock import MagicMock


@pytest.fixture
def valid_order_detail():
    """Gera uma carga válida de detalhes do pedido."""
    return {
        "order_id": "ord_98765432_uuid",
        "customer_id": "cust_123",
        "customer_email": "usuario@teste.com",
        "customer_tier": "vip",
        "order_type": "express",
        "total_amount": 299.90,
        "items": [
            {"product_id": "prod_100", "quantity": 1, "price": 299.90}
        ]
    }


def test_publish_order_placed_success(valid_order_detail, mocker):
    """Testa a publicação de evento no EventBridge com FailedEntryCount = 0."""
    mock_boto3 = mocker.patch("shared.event_publisher._get_eventbridge_client")
    mock_client = MagicMock()
    mock_client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [{"EventId": "evt_abc123"}]
    }
    mock_boto3.return_value = mock_client

    publisher = EventPublisher(event_bus_name="online-store-events")
    event_id = publisher.publish_order_placed(valid_order_detail)

    assert event_id == "evt_abc123"
    mock_client.put_events.assert_called_once()


def test_publish_order_placed_raises_error_when_failed_entry_count_greater_than_zero(valid_order_detail, mocker):
    """Testa se EventPublishError é lançado quando o EventBridge rejeita a entrada."""
    mock_boto3 = mocker.patch("shared.event_publisher._get_eventbridge_client")
    mock_client = MagicMock()
    mock_client.put_events.return_value = {
        "FailedEntryCount": 1,
        "Entries": [{"ErrorCode": "InternalFailure", "ErrorMessage": "Erro interno do EventBridge"}]
    }
    mock_boto3.return_value = mock_client

    publisher = EventPublisher(event_bus_name="online-store-events")

    with pytest.raises(EventPublishError):
        publisher.publish_order_placed(valid_order_detail)


def test_publish_order_placed_validation_error_on_invalid_payload():
    """Testa se o Pydantic v2 barra a publicação de eventos sem e-mail ou com quantidade zerada."""
    invalid_detail = {
        "order_id": "ord_bad",
        "customer_id": "cust_123",
        "customer_email": "usuario@teste.com",
        "total_amount": 100.0,
        "items": [
            {"product_id": "prod_1", "quantity": 0, "price": 100.0}  # quantity deve ser > 0
        ]
    }

    publisher = EventPublisher()

    with pytest.raises(ValidationError):
        publisher.publish_order_placed(invalid_detail)