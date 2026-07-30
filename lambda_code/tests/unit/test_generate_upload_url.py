import json
import pytest
from handlers.generate_upload_url import handler
from utils.event_factory import APIGatewayEventFactory


def test_generate_upload_url_success(s3_mock, mock_context):
    """
    Deverá retornar HTTP 200 e a Presigned URL de upload quando os parâmetros forem válidos.
    """
    # ARRANGE
    event = APIGatewayEventFactory.create_upload_url_post_event(
        product_id="prod_123",
        query_params={"type": "main", "content_type": "image/jpeg"}
    )

    # ACT
    response = handler(event, mock_context)

    # ASSERT
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "upload_url" in body
    assert body["object_key"] == "products/prod_123/main.jpg"
    assert body["expires_in"] == 3600


def test_generate_upload_url_missing_product_id(s3_mock, mock_context):
    """
    Deverá retornar HTTP 400 no formato ADR 0003 se o ID do produto for omitido.
    """
    # ARRANGE
    event = APIGatewayEventFactory.create_upload_url_post_event(product_id=None)

    # ACT
    response = handler(event, mock_context)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"]["type"] == "validation_error"
    assert "obrigatório" in body["error"]["message"]


def test_generate_upload_url_unsupported_content_type(s3_mock, mock_context):
    """
    Deverá retornar HTTP 400 se o Content-Type solicitado não for um tipo de imagem permitido.
    """
    # ARRANGE
    event = APIGatewayEventFactory.create_upload_url_post_event(
        product_id="prod_123",
        query_params={"content_type": "application/pdf"}
    )

    # ACT
    response = handler(event, mock_context)

    # ASSERT
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"]["type"] == "validation_error"
    assert "não suportado" in body["error"]["message"]