import time
import logging
from enum import Enum
from typing import Callable, Any

from shared.error_handler import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Máquina de Estados do Circuit Breaker (Disjuntor Distribuído).
    Protege a aplicação contra falhas em cascata ao consumir serviços externos instáveis.

    Estados:
      - CLOSED: Operação normal. Todas as chamadas passam para o serviço externo.
      - OPEN: Bloqueio imediato (Fast-Fail). Rejeita chamadas imediatamente sem tocar no serviço externo.
      - HALF_OPEN: Teste experimental. Permite chamadas de teste limitadas após o recovery_timeout.
    """

    def __init__(
            self,
            failure_threshold: int = 5,
            recovery_timeout: float = 30.0,
            success_threshold: int = 2
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0.0
        self.state = CircuitState.CLOSED

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        current_time = time.time()

        # Transição automática de OPEN para HALF_OPEN quando o timeout de recuperação expira
        if self.state == CircuitState.OPEN:
            if current_time - self.last_failure_time >= self.recovery_timeout:
                logger.warning("⏳ [CIRCUIT BREAKER] Timeout de recuperação expirado. Transicionando para HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                logger.error("🛑 [CIRCUIT BREAKER] Disjuntor ABERTO. Bloqueando chamada (Fast-Fail).")
                raise CircuitBreakerOpenError("Serviço de integração externo indisponível (Circuit Breaker OPEN).")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(
                f"✅ [CIRCUIT BREAKER] Chamada de teste bem-sucedida em HALF_OPEN "
                f"({self.success_count}/{self.success_threshold})."
            )
            if self.success_count >= self.success_threshold:
                logger.info("🟢 [CIRCUIT BREAKER] Limiar de sucesso atingido. Fechando disjuntor (CLOSED).")
                self.state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(f"⚠️ [CIRCUIT BREAKER] Falha registrada ({self.failure_count}/{self.failure_threshold}).")

        if self.failure_count >= self.failure_threshold:
            logger.critical("🔴 [CIRCUIT BREAKER] Limiar de falhas atingido! Abrindo disjuntor (OPEN).")
            self.state = CircuitState.OPEN