from unittest.mock import Mock
from shared.error_handler import RetryableError
from shared.resilience import retry_with_backoff

def test_decorator_should_retry_on_retryable_error_and_eventually_succeed(mocker):
    """
    Cenário: Uma função que falha nas 2 primeiras chamadas com RetryableError,
             mas tem sucesso na 3ª tentativa.
    Esperado: O decorador deve interceptar as falhas, esperar e retornar o sucesso.
    """
    operation_mock = Mock()
    operation_mock.side_effect = [
        RetryableError("Timeout intermitente 1"),
        RetryableError("Timeout intermitente 2"),
        "Sucesso do DynamoDB!"
    ]

    mocker.patch("time.sleep", return_value=None)

    @retry_with_backoff(max_attempts=3, base_delay=0.1)
    def decorated_function():
        return operation_mock()

    result = decorated_function()

    assert result == "Sucesso do DynamoDB!"
    assert operation_mock.call_count == 3