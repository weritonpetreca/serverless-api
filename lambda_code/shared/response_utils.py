import json
from decimal import Decimal
from typing import Any, Dict

def decimal_serializer(obj: Any) -> Any:
    """
    Serializador customizado para objetos do tipo Decimal.

    O DynamoDB retorna números (como preços e contadores) utilizando o tipo Decimal
    para evitar perda de precisão de ponto flutuante. Como o interpretador JSON nativo
    do Python não sabe serializar Deciamls, esta função intercepta esses tipos e os
    converte de forma segura antes da transmissão HTTP.
    """
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    raise TypeError(f"O objeto do tupo {type(obj)} não é serializável em JSON.")

def create_api_response(status_code:int, body_data: Any) -> Dict[str, Any]:
    """
    Formata uma resposta padrão para o formato exigido pelo AWS API Gateway Integration Proxy.

    Aplica os cabeçalhos de segurança CORS necessários e serializa o corpo da mensagem.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
        },
        "body": json.dumps(body_data, default=decimal_serializer)
    }

def create_success_response(status_code: int, data: Any) -> Dict[str, Any]:
    """Gera um envelope de resposta de sucesso (200 OK, 201 Created, etc)"""
    return create_api_response(status_code, data)

def create_error_response(status_code: int, error_message: str) -> Dict[str, Any]:
    """
    Gera um envelope padronizado para erros da API (400 Bad Request, 404 Not Found, etc).
    Garante que o cliente consuma um formato previsível: {"error": "mensagem de erro"}.
    """
    return create_api_response(status_code, {"error": error_message})