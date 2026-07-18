import os
import boto3
import pytest
from moto import mock_dynamodb

# ==============================================================================
# 🛡️ BLINDAGEM DO AMBIENTE (SHIFT-LEFT SECURITY)
# ==============================================================================
# Força o boto3 a usar credenciais falsas, garantindo que NENHUM teste
# tente bater acidentalmente na sua conta real da AWS Cloud.
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

os.environ["PRODUCTS_TABLE_NAME"] = "MockProductsTable"
os.environ["CATEGORY_GSI_NAME"] = "category-index"


@pytest.fixture(scope="function")
def dynamodb_mock():
    """
    Fixture corporativa para emular o Amazon DynamoDB em memória RAM.
    Cria a tabela e o Global Secondary Index (GSI) antes de cada teste.
    """
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        table = dynamodb.create_table(
            TableName=os.environ["PRODUCTS_TABLE_NAME"],
            KeySchema=[
                {"AttributeName": "id", "KeyType": "HASH"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "category", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": os.environ["CATEGORY_GSI_NAME"],
                    "KeySchema": [
                        {"AttributeName": "category", "KeyType": "HASH"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # O 'yield' age como o divisor de águas: entrega o controle para o teste rodar
        yield table

        # Após a execução do teste, o bloco 'with' fecha e limpa a memória RAM automaticamente