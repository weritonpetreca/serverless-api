import os
import boto3
import pytest
from moto import mock_dynamodb, mock_s3

# ==============================================================================
# 🛡️ BLINDAGEM DO AMBIENTE (SHIFT-LEFT SECURITY)
# ==============================================================================
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

os.environ["PRODUCTS_TABLE_NAME"] = "MockProductsTable"
os.environ["CATEGORY_GSI_NAME"] = "category-index"
os.environ["PRODUCT_IMAGE_BUCKET"] = "MockAssetsBucket"


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

        yield table


@pytest.fixture(scope="function")
def s3_mock():
    """
    Fixture corporativa para emular o Amazon S3 em memória RAM.
    Cria o bucket de mídias antes de cada teste.
    """
    with mock_s3():
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = os.environ["PRODUCT_IMAGE_BUCKET"]
        s3_client.create_bucket(Bucket=bucket_name)

        yield s3_client


@pytest.fixture(scope="function")
def mock_context():
    """
    Fixture corporativa que emula o objeto 'context' da AWS Lambda.
    """
    class LambdaContext:
        def __init__(self):
            self.aws_request_id = "req-corporate-default-id"
            self.function_name = "serverless-product-api-prod"
            self.memory_limit_in_mb = 128

    return LambdaContext()