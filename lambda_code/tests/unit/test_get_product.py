import json
from unittest.mock import patch
from get_product import handler
from error_handler import ProductNotFoundError
from utils.event_factory import APIGatewayEventFactory

@patch("get_product.repository")
def test_get_product_success(mock_repo):
    """Garante que busca por ID existente retorne o produto e HTTP 200."""
    # ARRANGE
    mock_product = {
        "id": "prod-111",
        "title": "Espada de Prata de Caçador",
        "category": "Accessories",
        "description": "Forjada para monstros.",
        "price": 850.00
    }
    mock_repo.get_by_id.return_value = mock_product
    event = {"pathParameters": {"id": "prod-111"}}

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "prod-111"
    assert body["title"] == "Espada de Prata de Caçador"
    mock_repo.get_by_id.assert_called_once_with("prod-111")


@patch("get_product.repository")
def test_get_product_not_found(mock_repo):
    """Garante retorno HTTP 404 caso o produto não exista no banco."""
    # ARRANGE
    mock_repo.get_by_id.return_value = None
    event = {"pathParameters": {"id": "prod-inexistente"}}

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "não encontrado" in body["error"]


@patch("get_product.repository")
def test_get_product_missing_id(mock_repo):
    """Garante retorno HTTP 400 caso o ID não seja enviado nos path parameters."""
    # ARRANGE
    event = {"pathParameters": {}}  # ID vazio/ausente

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "obrigatório" in body["error"]
    mock_repo.get_by_id.assert_not_called()


@patch("get_product.repository")
def test_get_product_internal_error(mock_repo):
    """Garante retorno HTTP 500 caso a comunicação com o DynamoDB falhe."""
    # ARRANGE
    mock_repo.get_by_id.side_effect = Exception("Falha de rede na AWS")
    event = {"pathParameters": {"id": "prod-111"}}

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Erro interno do servidor" in body["error"]["message"]

@patch("get_product.repository")
def test_handler_should_return_structured_404_when_product_not_found(mock_repo):
    """
    Cenário: Busca por um ID de produto inexistente.
    Esperado: Resposta HTTP 404 contendo o contrato JSON estrito da ADR 0003.
    """
    # 1. ARRANGE (Preparação do cenário)
    invalid_id = "prod_witcher_999"

    # Criamos o evento usando sua fábrica tática
    mock_event = APIGatewayEventFactory.create_get_event(product_id=invalid_id)

    # Criamos o contexto simulado da Lambda
    class MockContext:
        aws_request_id = "req-abc-123-xyz"
    mock_context = MockContext()

    # Em vez de return_value, usamos o side_effect no mock_repo que veio do decorator!
    mock_repo.get_by_id.side_effect = ProductNotFoundError(f"Product with ID {invalid_id} was not found.")

    # 2. ACT (Execução)
    response = handler(mock_event, mock_context)

    # 3. ASSERT (Validação do contrato da ADR 0003)
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