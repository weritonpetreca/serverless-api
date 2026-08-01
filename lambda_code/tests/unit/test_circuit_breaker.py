import time
import pytest
from shared.circuit_breaker import CircuitBreaker, CircuitState
from shared.error_handler import CircuitBreakerOpenError


def test_circuit_breaker_closed_state_success():
    """
    Deverá executar a função normalmente no estado CLOSED quando o serviço estiver saudável.
    """
    # ARRANGE
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
    mock_func = lambda x: x * 2

    # ACT
    result = cb.call(mock_func, 5)

    # ASSERT
    assert result == 10
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_circuit_breaker_opens_after_failure_threshold():
    """
    Deverá abrir o disjuntor (OPEN) após atingir o limite de falhas consecutivas.
    """
    # ARRANGE
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

    def failing_func():
        raise ValueError("Falha de integração com serviço externo")

    # ACT & ASSERT
    for i in range(3):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    # Disjuntor deve ter transicionado para OPEN
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 3


def test_circuit_breaker_fast_fails_when_open():
    """
    Deverá rejeitar chamadas imediatamente (Fast-Fail com CircuitBreakerOpenError) quando OPEN.
    """
    # ARRANGE
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)

    def failing_func():
        raise ValueError("Erro de serviço")

    # Força abertura do disjuntor com 2 falhas
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.state == CircuitState.OPEN

    # ACT & ASSERT: Próxima chamada deve ser bloqueada imediatamente (Fast-Fail)
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        cb.call(lambda: "não deve executar")

    assert "Circuit Breaker OPEN" in str(exc_info.value)


def test_circuit_breaker_transitions_to_half_open_and_closes():
    """
    Deverá transicionar para HALF_OPEN após o recovery_timeout e retornar a CLOSED após sucesso.
    """
    # ARRANGE: Timeout de recuperação curto de 0.1s e success_threshold=1
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, success_threshold=1)

    def failing_func():
        raise ValueError("Erro temporário")

    # Força abertura
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(failing_func)

    assert cb.state == CircuitState.OPEN

    # Aguarda o timeout de recuperação expirar
    time.sleep(0.15)

    # ACT: Chamada experimental no estado HALF_OPEN com função saudável
    result = cb.call(lambda: "sucesso_recuperacao")

    # ASSERT: Disjuntor deve ter retornado ao estado CLOSED
    assert result == "sucesso_recuperacao"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0