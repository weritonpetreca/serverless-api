import json
import pytest
from handlers.get_product import handler
from shared.error_handler import ProductNotFoundError
from utils.event_factory import APIGatewayEventFactory

@pytest.fixture
def mock_repo(mocker):
    """
    Fixture local que intercepta o repositório importado no handler.
    O pytest-mock (mocker) garante que o mock seja resetado a cada teste.
    """
    return mocker.patch("handlers.get_product.repository")

def test_get_product_success(mock_repo, mock_context):
    """Garante que busca por ID existente retorne o produto e HTTP 200."""
    mock_product = {
        "id": "prod-111",
        "title": "Espada de Prata de Caçador",
        "category": "Accessories",
        "description": "Forjada para monstros.",
        "price": 850.00
    }
    mock_repo.get_by_id.return_value = mock_product

    mock_event = APIGatewayEventFactory.create_get_event(mock_product["id"])

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "prod-111"
    assert body["title"] == "Espada de Prata de Caçador"
    mock_repo.get_by_id.assert_called_once_with("prod-111")

def test_get_product_missing_id(mock_repo, mock_context):
    """Garante retorno HTTP 400 caso o ID não seja enviado nos path parameters."""

    mock_event = APIGatewayEventFactory.create_get_event(product_id='')

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert "obrigatório" in body["error"]['message']
    mock_repo.get_by_id.assert_not_called()


def test_get_product_internal_error(mock_repo, mock_context):
    """Garante retorno HTTP 500 caso a comunicação com o DynamoDB falhe."""
    mock_repo.get_by_id.side_effect = Exception("Falha de rede na AWS")

    mock_event = APIGatewayEventFactory.create_get_event(product_id="prod-111")

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "internal_server_error"
    assert "Erro interno do servidor" in body["error"]["message"]

def test_handler_should_return_structured_404_when_product_not_found(mock_repo, mock_context):
    """
    Cenário: Busca por um ID de produto inexistente.
    Esperado: Resposta HTTP 404 contendo o contrato JSON estrito da ADR 0003.
    """
    invalid_id = "prod_witcher_999"

    mock_event = APIGatewayEventFactory.create_get_event(product_id=invalid_id)

    mock_context.aws_request_id = "req-abc-123-xyz"

    mock_repo.get_by_id.side_effect = ProductNotFoundError(f"Product with ID {invalid_id} was not found.")

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 404
    assert response["headers"]["Content-Type"] == "application/json"

    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "product_not_found"
    assert body["error"]["message"] == f"Product with ID {invalid_id} was not found."
    assert body["error"]["request_id"] == "req-abc-123-xyz"
    assert "timestamp" in body["error"]
    assert "suggestions" in body["error"]
    assert len(body["error"]["suggestions"]) > 0