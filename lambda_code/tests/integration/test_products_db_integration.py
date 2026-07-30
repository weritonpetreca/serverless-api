import os
import pytest
import boto3
from decimal import Decimal
from testcontainers.core.container import DockerContainer
from repository.products_db import ProductsRepository

# ==============================================================================
# 🐳 CONFIGURAÇÃO DO CONTAINER DOCKER (DYNAMODB LOCAL)
# ==============================================================================
@pytest.fixture(scope="module")
def dynamodb_service():
    """
    Sobe um container oficial do DynamoDB Local no Docker antes de iniciar os testes
    e o destrói automaticamente ao final da execução da suíte de integração.
    """
    # 1. Inicializa o container oficial da AWS
    container = DockerContainer("amazon/dynamodb-local:1.25.0")
    container.with_exposed_ports(8000)
    container.start()

    # 2. Obtém o IP e a Porta dinâmica mapeada pelo Docker na sua máquina
    host = container.get_container_host_ip()
    port = container.get_exposed_port(8000)
    endpoint_url = f"http://{host}:{port}"

    # 3. Cria fisicamente a tabela de produtos simulando o comportamento do CDK
    db_client = boto3.client(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="mock",
        aws_secret_access_key="mock"
    )

    db_client.create_table(
        TableName="IntegrationProductsTable",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "category", "AttributeType": "S"}
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "category-index",
                "KeySchema": [{"AttributeName": "category", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"}
            }
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    # 4. Injeta as configurações nas variáveis de ambiente temporárias do teste
    os.environ["PRODUCTS_TABLE_NAME"] = "IntegrationProductsTable"
    os.environ["CATEGORY_GSI_NAME"] = "category-index"

    # Sobrescreve o resource global do products_db para apontar para o container Docker
    from repository import products_db
    original_resource = products_db._dynamodb_resource
    products_db._dynamodb_resource = boto3.resource(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="mock",
        aws_secret_access_key="mock"
    )

    yield endpoint_url

    # 5. Teardown: Para e remove o container do Docker de forma limpa
    products_db._dynamodb_resource = original_resource
    container.stop()


# ==============================================================================
# 🎯 SUÍTE DE TESTES DE INTEGRAÇÃO
# ==============================================================================
def test_repository_save_and_get_by_id(dynamodb_service):
    """
    Valida a integração real de persistência e recuperação do DynamoDB.
    """
    # ARRANGE
    repo = ProductsRepository()
    new_product = {
        "id": "prod-456",
        "title": "Elixir de Gato",
        "category": "Home",
        "description": "Permite enxergar no escuro completo.",
        "price": Decimal("120.00")
    }

    # ACT (Salva no banco real do container)
    repo.save(new_product)

    # ASSERT (Recupera do banco real do container)
    retrieved = repo.get_by_id("prod-456")

    assert retrieved is not None
    assert retrieved["title"] == "Elixir de Gato"
    assert retrieved["price"] == Decimal("120.00")


def test_repository_update_dynamic_fields(dynamodb_service):
    """
    Valida se a montagem do UpdateExpression
    funciona fisicamente contra o motor oficial do DynamoDB.
    """
    # ARRANGE
    repo = ProductsRepository()
    product_id = "prod-456"
    update_payload = {
        "title": "Elixir de Gato Aprimorado",
        "price": Decimal("199.99")
    }

    # ACT (Atualiza parcialmente os campos)
    updated_fields = repo.update(product_id, update_payload)

    # ASSERT (Verifica se os campos alterados e antigos estão corretos)
    assert updated_fields is not None
    assert updated_fields["title"] == "Elixir de Gato Aprimorado"
    assert updated_fields["price"] == Decimal("199.99")
    # O campo description NÃO foi atualizado, mas deve continuar existindo intacto!
    assert updated_fields["description"] == "Permite enxergar no escuro completo."

def test_repository_add_image_to_product(dynamodb_service):
    """
    Valida fisicamente no container do DynamoDB Local a expressão atômica de anexar
    URLs e metadados às listas image_urls e images_metadata do produto.
    """
    # ARRANGE
    repo = ProductsRepository()
    product_id = "prod-789"
    initial_product = {
        "id": product_id,
        "title": "Mochila Tech",
        "category": "Accessories",
        "description": "Mochila à prova d'água.",
        "price": Decimal("250.00")
    }
    repo.save(initial_product)

    image_url = "https://MockAssetsBucket.s3.us-east-1.amazonaws.com/products/prod-789/main.jpg"
    metadata = {
        "image_url": image_url,
        "object_key": "products/prod-789/main.jpg",
        "file_size_bytes": 2048,
        "upload_date": "2026-07-30T12:00:00Z"
    }

    # ACT (Anexa a imagem)
    updated_attributes = repo.add_image_to_product(product_id, image_url, metadata)

    # ASSERT (Verifica se as listas foram criadas e preenchidas sem apagar outros campos)
    assert updated_attributes is not None
    assert "image_urls" in updated_attributes
    assert len(updated_attributes["image_urls"]) == 1
    assert updated_attributes["image_urls"][0] == image_url
    assert len(updated_attributes["images_metadata"]) == 1
    assert updated_attributes["images_metadata"][0]["file_size_bytes"] == 2048
    assert updated_attributes["title"] == "Mochila Tech"