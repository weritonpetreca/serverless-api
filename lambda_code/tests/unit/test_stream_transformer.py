import json
import base64
import pytest
from handlers.stream_transformer import handler

def _create_firehose_record(record_id: str, payload_dict: dict) -> dict:
    json_bytes = json.dumps(payload_dict).encode("utf-8")
    b64_data = base64.b64encode(json_bytes).decode("utf-8")
    return {
        "recordId": record_id,
        "data": b64_data
    }


def test_stream_transformer_enrichment_success(mocker):
    """Testa se a Lambda decodifica Base64, enriquece o produto no DynamoDB e retorna Ok com \\n."""
    mocker.patch(
        "handlers.stream_transformer.repository.get_by_id",
        return_value={"id": "prod_100", "title": "Teclado Mecânico RGB", "category": "Computers", "price": 350.00}
    )

    event_payload = {
        "event_type": "product_view",
        "user_id": "user_123",
        "product_id": "prod_100"
    }

    firehose_event = {
        "records": [_create_firehose_record("rec_001", event_payload)]
    }

    response = handler(firehose_event, None)

    assert "records" in response
    records = response["records"]
    assert len(records) == 1
    assert records[0]["recordId"] == "rec_001"
    assert records[0]["result"] == "Ok"

    # Decodifica a saída para verificar se os campos foram enriquecidos
    decoded_output = base64.b64decode(records[0]["data"]).decode("utf-8")
    assert decoded_output.endswith("\n")

    transformed_json = json.loads(decoded_output.strip())
    assert transformed_json["product_name"] == "Teclado Mecânico RGB"
    assert transformed_json["category"] == "Computers"
    assert transformed_json["price"] == 350.00


def test_stream_transformer_filters_test_users(mocker):
    """Testa se usuários de teste (test_*) são marcados com resultado 'Dropped'."""
    test_user_payload = {
        "event_type": "product_view",
        "user_id": "test_user_999",
        "product_id": "prod_100"
    }

    firehose_event = {
        "records": [_create_firehose_record("rec_002", test_user_payload)]
    }

    response = handler(firehose_event, None)

    records = response["records"]
    assert records[0]["result"] == "Dropped"


def test_stream_transformer_handles_corrupted_payload():
    """Testa se dados corrompidos são marcados com resultado 'ProcessingFailed'."""
    corrupted_event = {
        "records": [
            {
                "recordId": "rec_bad",
                "data": base64.b64encode(b"DADO_CORROMPIDO_NAO_JSON").decode("utf-8")
            }
        ]
    }

    response = handler(corrupted_event, None)

    records = response["records"]
    assert records[0]["result"] == "ProcessingFailed"