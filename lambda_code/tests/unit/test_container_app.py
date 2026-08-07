import sys
import json
import pytest
from pathlib import Path

# Adiciona dinamicamente a raiz do projeto ao sys.path
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from container_code.recommendation_service import app


@pytest.fixture
def client():
    """Fixture que fornece um cliente HTTP de teste do Flask."""
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_health_check_endpoint(client):
    """Testa o endpoint de checagem de saúde (/health) utilizado pelo ALB."""
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "healthy"
    assert data["service"] == "RecommendationEngineService"
    assert data["compute"] == "AWS Fargate"


def test_get_recommendations_endpoint_success(client, mocker):
    """Testa o endpoint de recomendação (/recommendations/<user_id>) simulando a busca via GSI no DynamoDB."""
    mock_table = mocker.patch("container_code.recommendation_service.table")
    mock_table.query.return_value = {
        "Items": [
            {"id": "prod_1", "title": "Teclado RGB", "category": "Computers", "price": "350.00"},
            {"id": "prod_2", "title": "Mouse Gamer", "category": "Computers", "price": "150.00"}
        ]
    }
    mocker.patch("container_code.recommendation_service._get_user_behavior_from_data_lake", return_value={"Computers": 5.0})

    response = client.get("/recommendations/user_dandelion")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["user_id"] == "user_dandelion"
    assert data["calculated_preferred_category"] == "Computers"
    assert data["recommendations_count"] == 2
    assert len(data["recommendations"]) == 2
    assert data["recommendations"][0]["title"] == "Teclado RGB"


def test_get_recommendations_endpoint_handles_exception(client, mocker):
    """Testa o tratamento de exceções no endpoint de recomendações retornando HTTP 500."""
    mock_table = mocker.patch("container_code.recommendation_service.table")
    mock_table.query.side_effect = RuntimeError("Falha de comunicação com o DynamoDB")

    response = client.get("/recommendations/user_123")

    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Failed to generate recommendations"