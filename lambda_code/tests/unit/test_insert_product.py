import json
from unittest.mock import patch
from insert_product import handler

# Usamos o patch para interceptar a instância global do repositório criada dentro do insert_product
@patch('insert_product.repository')
def test_insert_product_success(mock_repository):
    """
    Testa o cenário de sucesso na criação de um produto.
    Verifica se o status 201 é retornado, se um ID (UUID) foi gerado
    e se o méthod de persistência do repositório foi chamado.
    """
    event = {
        "body": json.dumps({
            "title": "Espada de Aço de Kaer Morhen",
            "category": "Home",
            "description": "Lâmina forjada em aço de meteorito, ideal contra humanos.",
            "price": 450.00
        })
    }

    response = handler(event, None)

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert "id" in body
    assert body["title"] == "Espada de Aço de Kaer Morhen"
    assert body["price"] == 450.00
    mock_repository.save.assert_called_once_with(body)


@patch('insert_product.repository')
def test_insert_product_validation_error_price(mock_repository):
    """
    Testa o fluxo de falha de validação (Preço negativo).
    Verifica se a Lambda barra a requisição com 400 Bad Request e não chama o banco.
    """
    event = {
        "body": json.dumps({
            "title": "Poção de Andorinha",
            "category": "Home",
            "description": "Acelera a regeneração de vida.",
            "price": -10.00
        })
    }

    response = handler(event, None)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])
    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert "validation_errors" in body["error"]["details"]
    mock_repository.save.assert_not_called()


def test_insert_product_empty_body():
    """
    Testa o comportamento da API quando o corpo da requisição está ausente.
    """
    # ARRANGE
    event = {}  # Sem a chave "body"

    from insert_product import handler

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "vazio ou ausente" in body["error"]

@patch("insert_product.repository")
def test_handler_should_return_structured_400_when_payload_has_invalid_category(mock_repo):
    """
    Cenário: Envio de um payload de produto com uma categoria não permitida no intetário.
    Esperado: Resposta HTTP 400 contendo o contrato JSON estrito da ADR 0003, detalhando o erro Pydantic.
    """
    invalid_body = {
        "title": "Poção de Raio",
        "category": "CategoriaInvalidaDeMonstros",
        "description": "Aumenta a velocidade dos reflexos do Bruxo",
        "price": 150.50
    }

    event = {"body": json.dumps(invalid_body)}

    class MockContext:
        aws_request_id = "req-insert-400-validation"
    mock_context = MockContext()

    response = handler(event, mock_context)

    assert response["statusCode"] == 400
    assert response["headers"]["Content-Type"] == "application/json"

    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"]["type"] == "validation_error"
    assert body["error"]["request_id"] == "req-insert-400-validation"
    assert "timestamp" in body["error"]
    assert "suggestions" in body["error"]

    mock_repo.save.assert_not_called()