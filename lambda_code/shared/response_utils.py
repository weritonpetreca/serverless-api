import json
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def decimal_serializer(obj: Any) -> Any:
    """
    Serializador customizado para objetos do tipo Decimal.
    Converte Decimals do DynamoDB para int ou float de forma segura.
    """
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, Exception):
        return str(obj)
    raise TypeError(f"O objeto do tipo {type(obj)} não é serializável em JSON.")


def create_api_response(status_code: int, body_data: Any) -> Dict[str, Any]:
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
    """Gera um envelope de resposta de sucesso (200 OK, 201 Created, etc)."""
    return create_api_response(status_code, data)


def create_error_response(
        status_code: int,
        error_type: str,
        message: str,
        request_id: str,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fábrica unificada para geração de envelopes de erro padronizados (ADR 0003).
    Elimina duplicidade de criação de dicionários de erro em todo o projeto.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    error_payload = {
        "error": {
            "type": error_type,
            "message": message,
            "timestamp": timestamp,
            "request_id": request_id,
            "details": details or {},
            "suggestions": suggestions or []
        }
    }
    return create_api_response(status_code, error_payload)