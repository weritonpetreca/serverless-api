import json
import pytest
from handlers.create_order import handler
from utils.event_factory import APIGatewayEventFactory


@pytest.fixture(autouse=True)
def mock_event_publisher(mocker):
    """Mock automático para o EventPublisher."""
    mock_eventbridge = mocker.patch("handlers.create_order.event_publisher")
    mock_eventbridge.publish_order_placed.return_value = "evt_order_123"
    return mock_eventbridge


def test_create_order_success(mock_context):
    """Garante que a compra via POST /orders retorna HTTP 201 Created."""
    order_payload = {
        "customer_id": "cust_geralt_100",
        "customer_email": "geralt@kaermorhen.com",
        "customer_tier": "vip",
        "order_type": "express",
        "total_amount": 850.00,
        "items": [
            {"product_id": "prod_espada_123", "quantity": 1, "price": 850.00}
        ]
    }

    mock_event = APIGatewayEventFactory.create_post_event(order_payload)
    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["status"] == "PROCESSING"
    assert "order_id" in body
    assert body["customer_id"] == "cust_geralt_100"


def test_create_order_validation_error_missing_email(mock_context):
    """Garante retorno HTTP 400 se o e-mail do cliente for omitido."""
    invalid_payload = {
        "customer_id": "cust_geralt_100",
        "total_amount": 850.00,
        "items": [
            {"product_id": "prod_espada_123", "quantity": 1, "price": 850.00}
        ]
    }

    mock_event = APIGatewayEventFactory.create_post_event(invalid_payload)
    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "validation_error"