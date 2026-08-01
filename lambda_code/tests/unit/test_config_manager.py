import time
import pytest
from botocore.exceptions import ClientError
from shared.config_manager import SSMParameterManager


def test_ssm_parameter_manager_cache_hit_and_miss(mocker):
    """
    Deverá buscar o parâmetro no SSM na primeira chamada (Cache Miss)
    e retornar da memória RAM local nas chamadas subsequentes (Cache Hit).
    """
    # ARRANGE
    manager = SSMParameterManager(ttl_seconds=300)
    mock_ssm = mocker.patch("shared.config_manager._get_ssm_client")
    mock_client = mock_ssm.return_value
    mock_client.get_parameter.return_value = {
        "Parameter": {"Name": "/store/dev/config/api_timeout", "Value": "10"}
    }

    # ACT: 1ª Chamada (Cache Miss - Vai ao SSM)
    val1 = manager.get_parameter("api_timeout", default_value="5")

    # ACT: 2ª Chamada (Cache Hit - Retorna da memória RAM)
    val2 = manager.get_parameter("api_timeout", default_value="5")

    # ASSERT
    assert val1 == "10"
    assert val2 == "10"
    # O cliente Boto3 SSM deve ter sido chamado exatamente UMA vez
    mock_client.get_parameter.assert_called_once_with(
        Name="/store/dev/config/api_timeout",
        WithDecryption=True
    )


def test_ssm_parameter_manager_fallback_on_client_error(mocker):
    """
    Deverá executar fallback gracioso para default_value quando o SSM lançar exceção.
    """
    # ARRANGE
    manager = SSMParameterManager(ttl_seconds=300)
    mock_ssm = mocker.patch("shared.config_manager._get_ssm_client")
    mock_client = mock_ssm.return_value
    mock_client.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "ParameterNotFound", "Message": "Parâmetro inexistente"}},
        "GetParameter"
    )

    # ACT
    value = manager.get_parameter("non_existent_param", default_value="fallback_value")

    # ASSERT
    assert value == "fallback_value"


def test_ssm_parameter_manager_ttl_expiration(mocker):
    """
    Deverá consultar o SSM novamente após o tempo de expiração do TTL.
    """
    # ARRANGE: TTL curto de 1 segundo
    manager = SSMParameterManager(ttl_seconds=1)
    mock_ssm = mocker.patch("shared.config_manager._get_ssm_client")
    mock_client = mock_ssm.return_value
    mock_client.get_parameter.side_effect = [
        {"Parameter": {"Value": "v1"}},
        {"Parameter": {"Value": "v2"}}
    ]

    # ACT
    v1 = manager.get_parameter("dynamic_param", default_value="default")
    time.sleep(1.1)  # Aguarda o TTL de 1s expirar
    v2 = manager.get_parameter("dynamic_param", default_value="default")

    # ASSERT
    assert v1 == "v1"
    assert v2 == "v2"
    assert mock_client.get_parameter.call_count == 2