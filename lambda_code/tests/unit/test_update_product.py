import json
from decimal import Decimal
from unittest.mock import patch
import pytest
from update_product import handler

@patch("update_product.repository")
def test_update_product_success(mock_repo):
    """Garante que a atualização parcial de campos válidos retorne HTTP 200 e os dados mesclados."""
    # ARRANGE
    product_id = "prod-999"
    # 1. Simula que o produto existe no banco
    mock_repo.get_by_id.return_value = {
        "id": product_id,
        "title": "Fone de Ouvido Antigo",
        "category": "Audio",
        "description": "Modelo com fio.",
        "price": Decimal("150.00")
    }
    # 2. Simula o retorno do update contendo os novos atributos mesclados
    mock_repo.update.return_value = {
        "id": product_id,
        "title": "Fone de Ouvido Novo",  # Alterado
        "category": "Audio",
        "description": "Modelo com fio.",
        "price": Decimal("299.99")   # Alterado
    }

    event = {
        "pathParameters": {"id": product_id},
        "body": json.dumps({
            "title": "Fone de Ouvido Novo",
            "price": 299.99
        })
    }

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["title"] == "Fone de Ouvido Novo"
    assert body["price"] == 299.99
    # O repository.update precisa ser chamado apenas com os campos fornecidos!
    mock_repo.update.assert_called_once_with(
        product_id,
        {"title": "Fone de Ouvido Novo", "price": Decimal("299.99")}
    )


@patch("update_product.repository")
def test_update_product_not_found(mock_repo):
    """Garante retorno HTTP 404 caso o produto não exista para atualização."""
    # ARRANGE
    mock_repo.get_by_id.return_value = None  # Produto inexistente
    event = {
        "pathParameters": {"id": "prod-inexistente"},
        "body": json.dumps({"price": 50.00})
    }

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "não existe" in body["error"]
    mock_repo.update.assert_not_called()


@patch("update_product.repository")
def test_update_product_validation_error(mock_repo):
    """Garante HTTP 400 se tentarmos atualizar campos com valores inválidos (regras de negócio)."""
    # ARRANGE
    product_id = "prod-999"
    mock_repo.get_by_id.return_value = {"id": product_id}

    # Payload com preço negativo e categoria inválida para estourar o Pydantic
    event = {
        "pathParameters": {"id": product_id},
        "body": json.dumps({
            "price": -15.00,
            "category": "ArmasDoBruxo"
        })
    }

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Falha na validação" in body["error"]
    assert "Detalhes" in body["error"]
    # Garante que as mensagens de validação customizadas estão presentes no erro
    assert "estritamente maior que zero" in body["error"] or "Categoria inválida" in body["error"]
    mock_repo.update.assert_not_called()


@patch("update_product.repository")
def test_update_product_missing_id(mock_repo):
    """Garante HTTP 400 se o ID do produto não for passado no path parameter."""
    # ARRANGE
    event = {
        "pathParameters": {},
        "body": json.dumps({"price": 100.00})
    }

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "URL é obrigatório" in body["error"]


@patch("update_product.repository")
def test_update_product_missing_body(mock_repo):
    """Garante HTTP 400 se o corpo do PATCH estiver vazio."""
    # ARRANGE
    event = {
        "pathParameters": {"id": "prod-123"},
        "body": ""
    }

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "não pode estar vazio" in body["error"]


@patch("update_product.repository")
def test_update_product_invalid_json(mock_repo):
    """Garante HTTP 400 para JSON mal formatado."""
    # ARRANGE
    event = {
        "pathParameters": {"id": "prod-123"},
        "body": "{invalid-json"
    }

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "mal formatado" in body["error"]