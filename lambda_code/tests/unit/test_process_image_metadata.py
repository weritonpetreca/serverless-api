import json
from decimal import Decimal
import pytest
from handlers import process_image_metadata
from handlers.process_image_metadata import handler
from repository.products_db import ProductsRepository
from utils.event_factory import APIGatewayEventFactory


def test_process_image_metadata_success(dynamodb_mock, s3_mock, mock_context):
    """
    Deverá processar o evento S3, consultar o head_object e registrar a imagem no DynamoDB.
    """
    # ARRANGE
    # Reassocia o repositório do módulo para utilizar o DynamoDB em memória do Moto
    process_image_metadata.repository = ProductsRepository()

    bucket_name = "MockAssetsBucket"
    object_key = "products/prod_123/main.jpg"

    repo = ProductsRepository()
    repo.save({
        "id": "prod_123",
        "title": "Teclado Mecânico",
        "category": "Computers",
        "description": "Switch Blue.",
        "price": Decimal("350.00")
    })

    s3_mock.put_object(Bucket=bucket_name, Key=object_key, Body=b"fake-image-bytes", ContentType="image/jpeg")
    s3_event = APIGatewayEventFactory.create_s3_event(bucket_name, object_key)

    # ACT
    response = handler(s3_event, mock_context)

    # ASSERT
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["processed_items"]) == 1
    assert body["processed_items"][0]["product_id"] == "prod_123"

    updated_product = repo.get_by_id("prod_123")
    assert len(updated_product["image_urls"]) == 1
    assert "main.jpg" in updated_product["image_urls"][0]


def test_process_image_metadata_empty_records(s3_mock, mock_context):
    """
    Deverá retornar HTTP 200 graciosamente caso o evento S3 não contenha registros.
    """
    # ARRANGE
    empty_event = {"Records": []}

    # ACT
    response = handler(empty_event, mock_context)

    # ASSERT
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Nenhum evento" in body["message"]