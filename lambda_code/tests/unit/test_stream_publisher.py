import pytest
from unittest.mock import MagicMock
from shared.stream_publisher import StreamPublisher


def test_send_activity_batch_success(mocker):
    """Testa a ingestão em lote no Amazon Data Firehose com 100% de sucesso."""
    mock_boto3 = mocker.patch("shared.stream_publisher._get_firehose_client")
    mock_client = MagicMock()
    mock_client.put_record_batch.return_value = {
        "FailedPutCount": 0,
        "RequestResponses": [{"RecordId": "rec_001"}]
    }
    mock_boto3.return_value = mock_client

    publisher = StreamPublisher(delivery_stream_name="customer-activity-stream")
    events = [
        {"event_type": "product_view", "user_id": "user_123", "product_id": "prod_100"}
    ]

    result = publisher.send_activity_batch(events)

    assert result["successful_count"] == 1
    assert result["failed_count"] == 0
    mock_client.put_record_batch.assert_called_once()


def test_send_activity_batch_handles_empty_list():
    """Testa se envio de lista vazia retorna contagens zeradas sem fazer chamadas Boto3."""
    publisher = StreamPublisher()
    result = publisher.send_activity_batch([])

    assert result["successful_count"] == 0
    assert result["failed_count"] == 0