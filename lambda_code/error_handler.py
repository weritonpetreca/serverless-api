import json
from decimal import Decimal
from datetime import datetime, timezone

class ProductNotFoundError(Exception):
    """Exceção lançada quando um produto não existe no DynamoDB."""
    pass

class ValidationError(Exception):
    """Exceção lançada para falhas de validação de dados de entrada ou parâmetros."""
    pass

class RetryableError(Exception):
    """Exceção para falhas intermitentes que podem ter sucesso em uma nova tentativa."""
    pass


class PermanentError(Exception):
    """Exceção para falhas críticas que não devem ser retentadas (ex: dados corrompidos)."""
    pass


class ErrorClassifier:
    """
    Componente centralizado para classificar exceções e
    formatar respostas de erro corporativas.
    """
    @staticmethod
    def _json_resilient_fallback(obj):
        """
        Função utilitária de fallback para garantir que o json.dumps nunca quebre
        ao interceptar tipos complexos vindos dos metadados do Pydantic.
        """
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, Exception):
            return str(obj)
        return str(obj)

    @staticmethod
    def handle_exception(exception: Exception, request_id: str) -> dict:
        """
        Casca vazia que temporariamente não trata nada.
        Retorna um dicionário vazio apenas para o teste poder rodar e falhar.
        """
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00",  "Z")
        exception_class_name = type(exception).__name__

        is_product_not_found = (
            isinstance(exception, ProductNotFoundError) or exception_class_name == "ProductNotFoundError"
        )
        is_validation_error = (
            isinstance(exception, ValidationError) or exception_class_name == "ValidationError"
        )

        if is_product_not_found:
            status_code = 404
            error_payload = {
                "error": {
                    "type": "product_not_found",
                    "message": str(exception),
                    "timestamp": timestamp,
                    "request_id": request_id,
                    "details": {},
                    "suggestions": [
                        "Verifique se o ID informado está correto.",
                        "Consulte o catálogo geral para garantir que o ID existe.",
                        "Tente novamente com um identificador válido."
                    ]
                }
            }

        elif is_validation_error:
            status_code = 400
            error_message = str(exception)

            details = {}
            if hasattr(exception, "errors") and callable(getattr(exception, "errors")):
                details["validation_errors"] = exception.errors()

            error_payload = {
                "error": {
                    "type": "validation_error",
                    "message": error_message,
                    "timestamp": timestamp,
                    "request_id": request_id,
                    "details": details,
                    "suggestions": [
                        "Corrija os parâmetros informados na requisição.",
                        "Certifique-se de que nenhum campo obrigatório foi omitido."
                    ]
                }
            }

        else:
            status_code = 500
            error_payload = {
                "error": {
                    "type": "internal_server_error",
                    "message": "Erro interno do servidor",
                    "timestamp": timestamp,
                    "request_id": request_id,
                    "details": {"internal_message": str(exception)},
                    "suggestions": [
                        "Ocorreu uma falha inesperada. Tente a operação novamente mais tarde.",
                        "Caso o erro persista, contate o time de suporte de infraestrutura."
                    ]
                }
            }
        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(error_payload, default=ErrorClassifier._json_resilient_fallback)
        }