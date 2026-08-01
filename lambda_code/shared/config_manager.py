import os
import time
import logging
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Boto3 client initialized lazily outside handler for Warm Starts
_ssm_client = None


def _get_ssm_client():
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


class SSMParameterManager:
    """
    Gerenciador centralizado para leitura de parâmetros do AWS Systems Manager (SSM) Parameter Store.
    Aplica cache local em memória RAM com tempo de expiração (TTL) para evitar chamadas
    repetidas à API do SSM, eliminando latência de I/O e custos por requisição.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.prefix = os.environ.get("SSM_CONFIG_PREFIX", "/store/dev/config").rstrip("/")
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, str] = {}
        self._cache_timestamps: Dict[str, float] = {}

    def get_parameter(self, param_name: str, default_value: str = "") -> str:
        """
        Busca um parâmetro no SSM Parameter Store sob a hierarquia configurada (ex: /store/dev/config/param_name).
        Retorna o valor em cache se o TTL ainda for válido; caso contrário, consulta a API do SSM.
        Em caso de erro na comunicação com o SSM, executa fallback silencioso para default_value.
        """
        clean_param_name = param_name.lstrip("/")
        full_path = f"{self.prefix}/{clean_param_name}"
        now = time.time()

        # 1. Verifica se o parâmetro está em cache e se o TTL permanece válido
        if full_path in self._cache:
            cache_age = now - self._cache_timestamps.get(full_path, 0.0)
            if cache_age < self.ttl_seconds:
                logger.debug(f"⚡ [SSM CACHE HIT] Parâmetro '{full_path}' recuperado da memória local.")
                return self._cache[full_path]

        # 2. Cache Miss: Consulta a API do SSM Parameter Store
        try:
            logger.info(f"🐢 [SSM CACHE MISS] Consultando SSM Parameter Store para: '{full_path}'")
            client = _get_ssm_client()
            response = client.get_parameter(Name=full_path, WithDecryption=True)
            param_value = response.get("Parameter", {}).get("Value", default_value)

            # Grava no cache em memória
            self._cache[full_path] = param_value
            self._cache_timestamps[full_path] = now
            return param_value

        except ClientError as e:
            logger.warning(
                f"Erro ao consultar parâmetro '{full_path}' no SSM: {str(e)}. "
                f"Usando valor padrão: '{default_value}'."
            )
            return default_value
        except Exception:
            logger.exception(
                f"Erro inesperado ao buscar parâmetro '{full_path}' no SSM:. "
                f"Usando valor padrão: '{default_value}'."
            )
            return default_value

    def is_feature_enabled(self, feature_name: str, default_enabled: bool = True) -> bool:
        """
        Verifica se uma Feature Flag está ativa no SSM Parameter Store de forma padronizada (DRY).
        Retorna True para valores 'true', '1', 'yes', 'on'; False para os demais.
        """
        default_str = "true" if default_enabled else "false"
        val = self.get_parameter(feature_name, default_value=default_str).strip().lower()
        return val in ("true", "1", "yes", "on")