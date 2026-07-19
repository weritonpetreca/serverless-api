import json
from decimal import Decimal
import pytest

from handlers.update_product import handler
from utils.event_factory import APIGatewayEventFactory

@pytest.fixture
def mock_repo(mocker):
    """
    Fixture local que intercepta o repositório importado no handler.
    O pytest-mock (mocker) garante que o mock seja resetado a cada teste.
    """
    return mocker.patch("handlers.update_product.repository")

def test_update_product_success(mock_repo, mock_context):
    """Garante que a atualização parcial de campos válidos retorne HTTP 200 e os dados mesclados."""
    product_id = "prod-999"

    mock_repo.get_by_id.return_value = {
        "id": product_id,
        "title": "Fone de Ouvido Antigo",
        "category": "Audio",
        "description": "Modelo com fio.",
        "price": Decimal("150.00")
    }

    mock_repo.update.return_value = {
        "id": product_id,
        "title": "Fone de Ouvido Novo",
        "category": "Audio",
        "description": "Modelo com fio.",
        "price": Decimal("299.99")
    }

    payload = {
        "title": "Fone de Ouvido Novo",
        "price": 299.99
    }

    mock_event = APIGatewayEventFactory.create_patch_event(product_id, payload)

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["title"] == "Fone de Ouvido Novo"
    assert body["price"] == 299.99
    mock_repo.update.assert_called_once_with(
        product_id,
        {"title": "Fone de Ouvido Novo", "price": Decimal("299.99")}
    )


def test_update_product_not_found(mock_repo, mock_context):
    """Garante retorno HTTP 404 caso o produto não exista para atualização."""
    mock_repo.get_by_id.return_value = None

    mock_event = APIGatewayEventFactory.create_patch_event("prod-inexistente", {"price": 50.00})
    mock_context.aws_request_id = "req-patch-404"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "product_not_found"
    assert "não existe" in body["error"]["message"]
    assert body["error"]["request_id"] == "req-patch-404"
    mock_repo.update.assert_not_called()


def test_update_product_validation_error(mock_repo, mock_context):
    """Garante HTTP 400 se tentarmos atualizar campos com valores inválidos (regras de negócio)."""
    product_id = "prod-999"

    payload = {
        "price": -15.00,
        "category": "ArmasDoBruxo"
    }

    mock_event = APIGatewayEventFactory.create_patch_event(product_id, payload)
    mock_context.aws_request_id = "req-patch-400-schema"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["request_id"] == "req-patch-400-schema"
    mock_repo.update.assert_not_called()


def test_update_product_missing_id(mock_repo, mock_context):
    """Garante HTTP 400 se o ID do produto não for passado no path parameter."""
    mock_event = APIGatewayEventFactory.create_patch_event('', {"price": 100.00})
    mock_context.aws_request_id = "req-patch-400-id"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert "parâmetro 'id'" in body["error"]["message"]
    assert "obrigatório" in body["error"]["message"]
    assert body["error"]["request_id"] == "req-patch-400-id"
    mock_repo.update.assert_not_called()


def test_update_product_missing_body(mock_repo, mock_context):
    """Garante HTTP 400 se o corpo do PATCH estiver vazio."""
    mock_event = APIGatewayEventFactory.create_patch_event("prod-123",{})
    mock_context.aws_request_id = "req-patch-400-body"

    response = handler(mock_event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert "não pode estar vazio" in body["error"]["message"]
    assert body["error"]["request_id"] == "req-patch-400-body"
    mock_repo.update.assert_not_called()


def test_update_product_invalid_json(mock_repo, mock_context):
    """Garante HTTP 400 para JSON mal formatado."""
    event = {
        "pathParameters": {"id": "prod-123"},
        "body": "{invalid-json"
    }
    mock_context.aws_request_id = "req-patch-400-syntax"

    response = handler(event, mock_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert "inválido" in body["error"]["message"]
    assert body["error"]["request_id"] == "req-patch-400-syntax"
    mock_repo.update.assert_not_called()