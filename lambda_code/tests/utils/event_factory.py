import json
from typing import Optional

class APIGatewayEventFactory:
    """
    Fábrica tática para gerar eventos simulados do Amazon API Gateway.
    Garante consistência de contratos em testes unitários Shift-Left.
    """

    @staticmethod
    def create_get_event(product_id: str, query_params: Optional[dict] = None) -> dict:
        """Gera um evento simulado para requisuções síncronas de busca (GET)."""
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