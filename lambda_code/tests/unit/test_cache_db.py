from decimal import Decimal
import pytest
import redis

from repository.cache_db import CacheRepository


def test_cache_repository_get_and_set_json(mocker):
    """
    Deverá gravar e recuperar com sucesso um objeto serializado em JSON no Valkey/Redis.
    """
    # ARRANGE
    repo = CacheRepository()
    mock_redis = mocker.patch.object(repo, "client")
    mock_redis.get.return_value = '{"id": "prod_1", "title": "Produto Teste", "price": 100.0}'

    test_payload = {"id": "prod_1", "title": "Produto Teste", "price": Decimal("100.00")}

    # ACT
    repo.set_json("product:prod_1", test_payload, ttl_seconds=3600)
    retrieved_data = repo.get_json("product:prod_1")

    # ASSERT
    mock_redis.set.assert_called_once()
    mock_redis.get.assert_called_once_with("product:prod_1")
    assert retrieved_data is not None
    assert retrieved_data["id"] == "prod_1"
    assert retrieved_data["price"] == 100.0


def test_cache_repository_graceful_degradation_on_error(mocker):
    """
    Deverá tratar exceções do Redis sem quebrar a aplicação (Graceful Degradation).
    """
    # ARRANGE
    repo = CacheRepository()
    mock_redis = mocker.patch.object(repo, "client")
    mock_redis.get.side_effect = redis.RedisError("Conexão recusada no cluster Valkey")

    # ACT
    result = repo.get_json("product:prod_1")

    # ASSERT (Retorna None graciosamente sem lançar exceção)
    assert result is None