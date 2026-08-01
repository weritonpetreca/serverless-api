import time
import random
import logging
from functools import wraps
from typing import Callable, Any
from shared.error_handler import RetryableError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FuncType = Callable[..., Any]


def retry_with_backoff(
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0
) -> Callable[[FuncType], FuncType]:
    """
    Decorador corporativo que implementa Exponential Backoff com Equal Jitter.
    Fórmula oficial AWS: wait_time = (exponential_delay / 2) + random.uniform(0, exponential_delay / 2)

    Garante um limite mínimo previsível de espera e distribui retentativas de forma estocástica
    para evitar o efeito manada (Thundering Herd).
    """
    def decorator(func: FuncType) -> FuncType:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except RetryableError as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        logger.error(
                            f"Limite máximo de {max_attempts} tentativas atingido. "
                            f"Disparando falha persistentemente."
                        )
                        raise e

                    # Algoritmo de Exponential Backoff com Equal Jitter da AWS
                    exponential_delay = min(max_delay, base_delay * (2 ** attempts))
                    half_delay = exponential_delay / 2.0
                    jittered_delay = half_delay + random.uniform(0, half_delay)

                    logger.warning(
                        f"Tentativa {attempts} falhou devido a um erro intermitente. "
                        f"Retentando em {jittered_delay:.2f}s com Equal Jitter. Erro: {str(e)}"
                    )

                    time.sleep(jittered_delay)
        return wrapper
    return decorator

# Alias opcional para legibilidade de código
retry_with_equal_jitter = retry_with_backoff