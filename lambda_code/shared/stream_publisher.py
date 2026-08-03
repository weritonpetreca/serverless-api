import json
import logging
import os
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

from domain.stream_schema import CustomerActivityRecord
from shared.error_handler import RetryableError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_firehose_client = None


def _get_firehose_client():
    global _firehose_client
    if _firehose_client is None:
        _firehose_client = boto3.client("firehose")
    return _firehose_client


class StreamPublisher:
    """
    Utilitário para ingestão em lote de eventos de atividade do cliente no Amazon Data Firehose.
    Aplica validação Pydantic v2 e verificação de FailedPutCount.
    """

    def __init__(self, delivery_stream_name: Optional[str] = None) -> None:
        self.stream_name = delivery_stream_name or os.environ.get("FIREHOSE_STREAM_NAME", "customer-activity-stream")

    def send_activity_batch(self, activity_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Envia um lote de até 500 registros de atividade para o Amazon Data Firehose via put_record_batch.
        """
        if not activity_events:
            return {"successful_count": 0, "failed_count": 0}

        try:
            firehose_records = []
            for event_data in activity_events:
                # Valida o evento com Pydantic v2
                validated_event = CustomerActivityRecord.model_validate(event_data)
                json_str = json.dumps(validated_event.model_dump()) + "\n"

                firehose_records.append({
                    "Data": json_str.encode("utf-8")
                })

            logger.info(f"Enviando lote de {len(firehose_records)} registro(s) para o Firehose '{self.stream_name}'")
            client = _get_firehose_client()
            response = client.put_record_batch(
                DeliveryStreamName=self.stream_name,
                Records=firehose_records
            )

            failed_count = response.get("FailedPutCount", 0)
            successful_count = len(firehose_records) - failed_count

            if failed_count > 0:
                logger.warning(f"⚠️ {failed_count} registro(s) falharam na ingestão do Firehose.")

            logger.info(f"Ingestão Firehose concluída. Sucessos: {successful_count}, Falhas: {failed_count}")
            return {"successful_count": successful_count, "failed_count": failed_count}

        except ClientError as e:
            logger.exception("Erro no SDK Boto3 ao enviar lote para o Amazon Data Firehose.")
            raise RetryableError(f"Instabilidade de comunicação com o Firehose: {str(e)}")

        except Exception:
            logger.exception("Erro inesperado ao enviar lote para o Firehose.")
            raise