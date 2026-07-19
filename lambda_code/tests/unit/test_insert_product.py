import json
import pytest
from handlers.insert_product import handler
from utils.event_factory import APIGatewayEventFactory

@pytest.fixture
def mock_repo(mocker):
    """
    Fixture local que intercepta o repositório importado no handler.
    O pytest-mock (mocker) garante que o mock seja resetado a cada teste.
    """
    return mocker.patch('handlers.insert_product.repository')

def test_insert_product_success(mock_repo, mock_context):
    """
    Testa o cenário de sucesso na criação de um produto.
    Verifica se o status 201 é retornado, se um ID (UUID) foi gerado
    e se o method de persistência do repositório foi chamado.
    """
    mock_event = APIGatewayEventFactory.create_post_event({
        "title": "Espada de Aço de Kaer Morhen",
        "category": "Home",
        "description": "Lâmina forjada em aço de meteorito, ideal contra humanos.",
        "price": 450.00
    })
    mock_context.aws_request_id = "req-insert-201-success"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert "id" in body
    assert body["title"] == "Espada de Aço de Kaer Morhen"
    assert body["price"] == 450.00
    mock_repo.save.assert_called_once_with(body)


def test_insert_product_validation_error_price(mock_repo, mock_context):
    """
    Testa o fluxo de falha de validação de esquema (Preço negativo).
    Verifica se a Lambda barra com HTTP 400 estruturado de acordo com a ADR 0003.
    """
    mock_event = APIGatewayEventFactory.create_post_event({
        "title": "Poção de Andorinha",
        "category": "Home",
        "description": "Acelera a regeneração de vida.",
        "price": -10.00
    })
    mock_context.aws_request_id = "req-insert-400-price"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["request_id"] == "req-insert-400-price"
    assert "timestamp" in body["error"]
    assert "suggestions" in body["error"]

    assert "price" in body["error"]["message"].lower()
    mock_repo.save.assert_not_called()


def test_insert_product_empty_body(mock_repo, mock_context):
    """
    Garante retorno HTTP 400 estruturado quando o corpo da requisição
    estiver totalmente vazio ou ausente (DomainValidationError).
    """
    mock_event = APIGatewayEventFactory.create_post_event({})
    mock_context.aws_request_id = "req-insert-400-empty"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert "vazio ou ausente" in body["error"]["message"]
    assert body["error"]["request_id"] == "req-insert-400-empty"
    mock_repo.save.assert_not_called()


def test_handler_should_return_structured_400_when_payload_has_invalid_category(mock_repo, mock_context):
    """
    Cenário: Envio de um payload de produto com uma categoria não permitida no itinerário.
    Esperado: Resposta HTTP 400 contendo o contrato JSON estrito da ADR 0003.
    """
    invalid_body = {
        "title": "Poção de Raio",
        "category": "CategoriaInvalidaDeMonstros",
        "description": "Aumenta a velocidade dos reflexos do Bruxo",
        "price": 150.50
    }
    mock_event = APIGatewayEventFactory.create_post_event(invalid_body)
    mock_context.aws_request_id = "req-insert-400-category"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    assert response["headers"]["Content-Type"] == "application/json"

    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["request_id"] == "req-insert-400-category"
    assert "timestamp" in body["error"]
    assert "suggestions" in body["error"]
    mock_repo.save.assert_not_called()


def test_insert_product_invalid_json_syntax(mock_repo, mock_context):
    """
    Cenário: Envio de uma string que não consegue ser parseada como JSON (Ex: aspas faltando).
    Esperado: Captura de json.JSONDecodeError e conversão em HTTP 400 ValidationError.
    """
    mock_event = {
        "httpMethod": "POST",
        "body": "{'title': Espada Incompleta, 'price': 100"
    }
    mock_context.aws_request_id = "req-insert-400-syntax"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert "Formato JSON inválido" in body["error"]["message"]
    assert body["error"]["request_id"] == "req-insert-400-syntax"
    mock_repo.save.assert_not_called()