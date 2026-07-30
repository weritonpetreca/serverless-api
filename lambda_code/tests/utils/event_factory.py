import json
from typing import Optional


class APIGatewayEventFactory:
    """
    Fábrica tática para gerar eventos simulados do Amazon API Gateway e Amazon S3.
    Garante consistência de contratos em testes unitários Shift-Left.
    """

    @staticmethod
    def create_get_event(product_id: str, query_params: Optional[dict] = None) -> dict:
        """Gera um evento simulado para requisições síncronas de busca (GET)."""
        return {
            "httpMethod": "GET",
            "path": f"/products/{product_id}" if product_id else "/products",
            "pathParameters": {"id": product_id} if product_id else None,
            "queryStringParameters": query_params,
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            "body": None,
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request-id-12345",
                "stage": "prod"
            }
        }

    @staticmethod
    def create_post_event(payload: dict) -> dict:
        """Gera um evento simulado para requisições de criação de dados (POST)."""
        return {
            "httpMethod": "POST",
            "path": "/products",
            "pathParameters": None,
            "queryStringParameters": None,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(payload) if payload else None,
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request-id-67890",
                "stage": "prod"
            }
        }

    @staticmethod
    def create_patch_event(product_id: str, payload: dict) -> dict:
        """Gera um evento simulado para requisições de atualização parcial (PATCH)."""
        return {
            "httpMethod": "PATCH",
            "path": f"/products/{product_id}",
            "pathParameters": {"id": product_id},
            "queryStringParameters": None,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(payload) if payload else None,
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request-id-abcde",
                "stage": "prod"
            }
        }

    @staticmethod
    def create_upload_url_post_event(product_id: str, query_params: Optional[dict] = None) -> dict:
        """Gera um evento simulado para solicitação de URL pré-assinada de upload."""
        return {
            "httpMethod": "POST",
            "path": f"/products/{product_id}/upload-url",
            "pathParameters": {"id": product_id} if product_id else None,
            "queryStringParameters": query_params,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": None,
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request-id-upload-123",
                "stage": "prod"
            }
        }

    @staticmethod
    def create_s3_event(bucket_name: str, object_key: str) -> dict:
        """Gera um evento simulado de notificação de upload do Amazon S3 (s3:ObjectCreated:*)."""
        return {
            "Records": [
                {
                    "eventVersion": "2.1",
                    "eventSource": "aws:s3",
                    "awsRegion": "us-east-1",
                    "eventTime": "2026-07-30T12:00:00.000Z",
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "bucket": {
                            "name": bucket_name,
                            "arn": f"arn:aws:s3:::{bucket_name}"
                        },
                        "object": {
                            "key": object_key,
                            "size": 1024
                        }
                    }
                }
            ]
        }