import os
import json
import logging
from typing import Any, Optional
from shared.response_utils import decimal_serializer
import redis

logger = logging.getLogger(__name__)


class CacheRepository:
    """
    Camada de Abstração de Cache em Memória para o Amazon ElastiCache (Valkey / Redis).
    Garante resiliência (Graceful Degradation): falhas de comunicação no Valkey são capturadas
    e logadas sem interromper o fluxo da aplicação.
    """

    def __init__(self) -> None:
        self.host = os.environ.get("REDIS_HOST", "localhost")
        self.port = int(os.environ.get("REDIS_PORT", "6379"))

        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0
            )
        except Exception as e:
            logger.warning(f"Não foi possível inicializar o cliente Valkey/Redis: {str(e)}")
            self.client = None

    def get_json(self, key: str) -> Optional[Any]:
        """
        Busca uma chave no cache Valkey/Redis e desserializa a string JSON.
        Retorna None se a chave não existir (Cache Miss) ou em caso de falha na rede.
        """
        if not self.client:
            return None
        try:
            data = self.client.get(key)
            if data:
                logger.info(f"⚡ [CACHE HIT] Dado localizado no Redis para a chave: {key}")
                return json.loads(data)
            logger.info(f"🐢 [CACHE MISS] Dado não encontrado no Redis para a chave: {key}")
            return None
        except redis.RedisError as e:
            logger.warning(f"Erro ao buscar chave '{key}' no Redis: {str(e)}. Executando fallback para o DynamoDB.")
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """
        Armazena um objeto no cache Valkey/Redis serializado em JSON com tempo de expiração (TTL).
        """
        if not self.client:
            return
        try:
            serialized_data = json.dumps(value, default=decimal_serializer)
            self.client.set(name=key, ex=ttl_seconds, value=serialized_data)
            logger.info(f"Gravação no Redis concluída com sucesso. Chave: '{key}' (TTL: {ttl_seconds}s)")
        except redis.RedisError as e:
            logger.warning(f"Erro ao salvar chave '{key}' no cache Redis: {str(e)}.")

    def delete(self, key: str) -> None:
        """
        Remove uma chave do cache Valkey/Redis (Invalidação Explícita).
        """
        if not self.client:
            return
        try:
            self.client.delete(key)
            logger.info(f"Invalidação de cache executada. Chave removida: '{key}'")
        except redis.RedisError as e:
            logger.warning(f"Erro ao deletar chave '{key}' no cache Redis: {str(e)}.")