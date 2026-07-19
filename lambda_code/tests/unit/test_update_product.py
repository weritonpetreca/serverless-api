import json
from decimal import Decimal
from unittest.mock import patch
import pytest
from update_product import handler
from utils.event_factory import APIGatewayEventFactory


@patch("update_product.repository")
def test_update_product_success(mock_repo):
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

    response = handler(mock_event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["title"] == "Fone de Ouvido Novo"
    assert body["price"] == 299.99
    mock_repo.update.assert_called_once_with(
        product_id,
        {"title": "Fone de Ouvido Novo", "price": Decimal("299.99")}
    )


@patch("update_product.repository")
def test_update_product_not_found(mock_repo):
    """Garante retorno HTTP 404 caso o produto não exista para atualização."""
    mock_repo.get_by_id.return_value = None

    mock_event = APIGatewayEventFactory.create_patch_event("prod-inexistente", {"price": 50.00})

    response = handler(mock_event, None)

    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "não existe" in body["error"]
    mock_repo.update.assert_not_called()


@patch("update_product.repository")
def test_update_product_validation_error(mock_repo):
    """Garante HTTP 400 se tentarmos atualizar campos com valores inválidos (regras de negócio)."""
    product_id = "prod-999"

    payload = {
        "price": -15.00,
        "category": "ArmasDoBruxo"
    }

    mock_repo.get_by_id.return_value = {"id": product_id}

    mock_event = APIGatewayEventFactory.create_patch_event(product_id, payload)

    response = handler(mock_event, None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Falha na validação" in body["error"]
    assert "Detalhes" in body["error"]
    assert "estritamente maior que zero" in body["error"] or "Categoria inválida" in body["error"]
    mock_repo.update.assert_not_called()


@patch("update_product.repository")
def test_update_product_missing_id(mock_repo):
    """Garante HTTP 400 se o ID do produto não for passado no path parameter."""
    mock_event = APIGatewayEventFactory.create_patch_event('', {"price": 100.00})

    response = handler(mock_event, None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "URL é obrigatório" in body["error"]


@patch("update_product.repository")
def test_update_product_missing_body(mock_repo):
    """Garante HTTP 400 se o corpo do PATCH estiver vazio."""
    mock_event = APIGatewayEventFactory.create_patch_event("prod-123",{})

    response = handler(mock_event, None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "não pode estar vazio" in body["error"]


@patch("update_product.repository")
def test_update_product_invalid_json(mock_repo):
    """Garante HTTP 400 para JSON mal formatado."""
    event = {
        "pathParameters": {"id": "prod-123"},
        "body": "{invalid-json"
    }

    response = handler(event, None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "mal formatado" in body["error"]