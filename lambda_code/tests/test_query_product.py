import json
from unittest.mock import patch
from query_products import handler

@patch("query_products.repository")
def test_query_products_by_category_success(mock_repo):
    """Garante que a busca retorne a lista de produtos da categoria informada."""
    # ARRANGE
    mock_list = [
        {"id": "prod-1", "title": "Placa de Vídeo", "category": "Computers", "price": 1500.00},
        {"id": "prod-2", "title": "Teclado Mecânico", "category": "Computers", "price": 300.00}
    ]
    mock_repo.find_by_category.return_value = mock_list
    event = {"queryStringParameters": {"category": "Computers"}}

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 2
    assert body[0]["title"] == "Placa de Vídeo"
    mock_repo.find_by_category.assert_called_once_with("Computers")


@patch("query_products.repository")
def test_query_products_missing_category(mock_repo):
    """Garante HTTP 400 se a categoria não for informada na query string."""
    # ARRANGE
    event = {"queryStringParameters": {}}  # Sem o parâmetro 'category'

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "obrigatório" in body["error"]
    mock_repo.find_by_category.assert_not_called()


@patch("query_products.repository")
def test_query_products_internal_error(mock_repo):
    """Garante HTTP 500 caso o GSI lance uma exceção."""
    # ARRANGE
    mock_repo.find_by_category.side_effect = Exception("GSI Inacessível")
    event = {"queryStringParameters": {"category": "Computers"}}

    # ACT
    response = handler(event, None)

    # ASSERT
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Erro interno" in body["error"]