import json
from unittest.mock import patch
import pytest
from pydantic import ValidationError

# Usamos o patch para interceptar a instância global do repositório criada dentro do insert_product
@patch('insert_product.repository')
def test_insert_product_success(mock_repository):
    """
    Testa o cenário de sucesso na criação de um produto.
    Verifica se o status 201 é retornado, se um ID (UUID) foi gerado
    e se o méthod de persistência do repositório foi chamado.
    """
    # ARRANGE (Preparação)
    # Simulamos o evento de entrada que o API Gateway enviaria para a Lambda
    event = {
        "body": json.dumps({
            "title": "Espada de Aço de Kaer Morhen",
            "category": "Home",
            "description": "Lâmina forjada em aço de meteorito, ideal contra humanos.",
            "price": 450.00
        })
    }

    # Importamos o handler localmente para garantir que o mock seja aplicado antes da importação
    from insert_product import handler

    # ACT (Ação)
    response = handler(event, None)

    # ASSERT (Verificação)
    assert response["statusCode"] == 201

    body = json.loads(response["body"])
    assert "id" in body  # O ID precisa ter sido gerado no backend
    assert body["title"] == "Espada de Aço de Kaer Morhen"
    assert body["price"] == 450.00

    # Garante que a Lambda de fato chamou o method save do banco de dados uma vez
    mock_repository.save.assert_called_once_with(body)


@patch('insert_product.repository')
def test_insert_product_validation_error(mock_repository):
    """
    Testa o fluxo de falha de validação (Preço negativo).
    Verifica se a Lambda barra a requisição com 400 Bad Request e não chama o banco.
    """
    # ARRANGE
    event = {
        "body": json.dumps({
            "title": "Poção de Andorinha",
            "category": "Home",
            "description": "Acelera a regeneração de vida.",
            "price": -10.00
        })
    }

    from insert_product import handler

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400

    body = json.loads(response["body"])
    assert "error" in body
    assert "Campo 'price'" in body["error"]

    # Segurança: O repositório de banco de dados NUNCA deve ser chamado se a validação falhar!
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