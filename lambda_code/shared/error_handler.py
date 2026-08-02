import logging
from shared.response_utils import create_error_response

logger = logging.getLogger(__name__)


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


class CircuitBreakerOpenError(Exception):
    """Exceção lançada quando uma chamada para serviço externo é bloqueada por disjuntor ABERTO."""
    pass


class EventPublishError(Exception):
    """Exceção lançada quando a publicação de um evento no Amazon EventBridge falha."""
    pass


class OrderProcessingException(Exception):
    """Exceção lançada quando o processador assíncrono SQS falha no processamento do pedido."""
    pass


class ErrorClassifier:
    """
    Componente centralizado para classificar exceções e
    formatar respostas de erro corporativas via response_utils.
    """

    @staticmethod
    def handle_exception(exception: Exception, request_id: str) -> dict:
        exception_class_name = type(exception).__name__

        is_product_not_found = (
                isinstance(exception, ProductNotFoundError) or exception_class_name == "ProductNotFoundError"
        )
        is_validation_error = (
                isinstance(exception, ValidationError) or exception_class_name == "ValidationError"
        )
        is_circuit_open = (
                isinstance(exception, CircuitBreakerOpenError) or exception_class_name == "CircuitBreakerOpenError"
        )
        is_event_publish_error = (
                isinstance(exception, EventPublishError) or exception_class_name == "EventPublishError"
        )

        if is_product_not_found:
            return create_error_response(
                status_code=404,
                error_type="product_not_found",
                message=str(exception),
                request_id=request_id,
                suggestions=[
                    "Verifique se o ID informado está correto.",
                    "Consulte o catálogo geral para garantir que o ID existe.",
                    "Tente novamente com um identificador válido."
                ]
            )

        elif is_validation_error:
            error_message = str(exception)
            details = {}
            if hasattr(exception, "errors") and callable(getattr(exception, "errors")):
                details["validation_errors"] = exception.errors()

            return create_error_response(
                status_code=400,
                error_type="validation_error",
                message=error_message,
                request_id=request_id,
                details=details,
                suggestions=[
                    "Corrija os parâmetros informados na requisição.",
                    "Certifique-se de que nenhum campo obrigatório foi omitido."
                ]
            )

        elif is_circuit_open:
            return create_error_response(
                status_code=503,
                error_type="service_unavailable",
                message=str(exception),
                request_id=request_id,
                details={"circuit_breaker_state": "OPEN"},
                suggestions=[
                    "O serviço de integração externo está indisponível no momento.",
                    "O sistema bloqueou chamadas repetidas para evitar sobrecarga. Tente novamente em alguns minutos."
                ]
            )

        elif is_event_publish_error:
            return create_error_response(
                status_code=502,
                error_type="bad_gateway",
                message="Falha ao publicar evento no barramento de eventos.",
                request_id=request_id,
                details={"internal_message": str(exception)},
                suggestions=[
                    "O barramento de eventos sofreu uma instabilidade temporária.",
                    "O sistema tentará republicar a mensagem de forma assíncrona."
                ]
            )

        else:
            return create_error_response(
                status_code=500,
                error_type="internal_server_error",
                message="Erro interno do servidor",
                request_id=request_id,
                details={"internal_message": str(exception)},
                suggestions=[
                    "Ocorreu uma falha inesperada. Tente a operação novamente mais tarde.",
                    "Caso o erro persista, contate o time de suporte de infraestrutura."
                ]
            )