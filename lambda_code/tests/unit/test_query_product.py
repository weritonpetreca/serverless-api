import json
import pytest
from handlers.query_products import handler
from utils.event_factory import APIGatewayEventFactory


@pytest.fixture
def mock_repo(mocker):
    """
    Fixture local que intercepta o repositório importado no handler.
    O pytest-mock (mocker) garante que o mock seja resetado a cada teste.
    """
    return mocker.patch("handlers.query_products.repository")

def test_query_products_by_category_success(mock_repo):
    """Garante que a busca retorne a lista de produtos da categoria informada."""
    mock_list = [
        {"id": "prod-1", "title": "Placa de Vídeo", "category": "Computers", "price": 1500.00},
        {"id": "prod-2", "title": "Teclado Mecânico", "category": "Computers", "price": 300.00}
    ]
    mock_repo.find_by_category.return_value = mock_list

    mock_event = APIGatewayEventFactory.create_get_event('',{"category": "Computers"})

    response = handler(mock_event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 2
    assert body[0]["title"] == "Placa de Vídeo"
    mock_repo.find_by_category.assert_called_once_with("Computers")


def test_query_products_missing_category(mock_repo, mock_context):
    """Garante HTTP 400 se a categoria não for informada na query string."""
    mock_event = APIGatewayEventFactory.create_get_event('',{})

    mock_context.aws_request_id = "req-query-400"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["request_id"] == "req-query-400"
    assert "timestamp" in body["error"]
    assert "suggestions" in body["error"]
    mock_repo.find_by_category.assert_not_called()


def test_query_products_internal_error(mock_repo, mock_context):
    """Garante HTTP 500 caso o GSI lance uma exceção."""
    mock_repo.find_by_category.side_effect = Exception("GSI Inacessível no DynamoDB")

    mock_event = APIGatewayEventFactory.create_get_event('', {"category": "Computers"})

    mock_context.aws_request_id = "req-query-500"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "internal_server_error"
    assert body["error"]["request_id"] == "req-query-500"
    mock_repo.find_by_category.assert_called_once_with("Computers")