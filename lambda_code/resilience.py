import time
import random
import logging
from functools import wraps
from typing import Callable, Any
from error_handler import RetryableError

logger = logging.getLogger(__name__)

FuncType = Callable[..., Any]

def retry_with_backoff(
        max_attempts: int = 3,
        base_delay: float = 0.5
) -> Callable[[FuncType], FuncType]:
    """
    Decorador corporativo que implementa a estratégia de
    Exponential Backoff com Full Jitter para operações recuperáveis.
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
                            f"Limite máximo de {max_attempts} tentativas atingido."
                            f"Disparando falha persistente."
                        )
                        raise e

                    calculated_delay = base_delay * (2 ** attempts)
                    jittered_delay = random.uniform(0, calculated_delay)

                    logger.warning(
                        f"Tentativa {attempts} falhou devido a um erro intermitente."
                        f"Retentando em {jittered_delay:.2f} segundos. Erro: {str(e)}"
                    )

                    time.sleep(jittered_delay)
        return wrapper
    return decorator