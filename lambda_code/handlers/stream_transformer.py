import json
import base64
import logging
from typing import Dict, Any, List, Tuple
from repository.products_db import ProductsRepository
from domain.stream_schema import CustomerActivityRecord

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicialização do repositório no escopo global para reaproveitamento em Warm Starts
repository = ProductsRepository()


def _transform_single_record(
        payload_dict: Dict[str, Any],
        local_product_cache: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    """
    Função auxiliar para transformar, enriquecer ou filtrar um único registro de stream.
    Retorna a tupla (status, payload_transformada), onde status pode ser 'Ok' ou 'Dropped'.
    """
    user_id = payload_dict.get("user_id", "")

    # 1. Filtragem: Descarta atividade de usuários de teste e bots usando tupla no startswith (SonarQube OK)
    if user_id.startswith(("test_", "bot_")):
        logger.info(f"🚫 [FIREHOSE FILTER] Registro de teste/bot descartado para user_id: {user_id}")
        return "Dropped", payload_dict

    # 2. Enriquecimento: Se for visualização de produto, consulta o DynamoDB usando o Cache do Lote
    event_type = payload_dict.get("event_type")
    product_id = payload_dict.get("product_id")

    if event_type == "product_view" and product_id:
        try:
            if product_id not in local_product_cache:
                response = repository.table.get_item(Key={"id": product_id})
                local_product_cache[product_id] = response.get("Item")

            product = local_product_cache[product_id]
            if product:
                payload_dict["product_name"] = product.get("title")
                payload_dict["category"] = product.get("category")
                payload_dict["price"] = float(product.get("price", 0.0))
                logger.info(f"✨ [FIREHOSE ENRICH] Registro enriquecido para produto ID: {product_id}")
        except Exception:
            logger.exception(f"Falha não-bloqueante ao enriquecer produto ID {product_id} no DynamoDB.")

    # Validação do modelo com Pydantic v2
    validated_model = CustomerActivityRecord.model_validate(payload_dict)
    return "Ok", validated_model.model_dump()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler da AWS Lambda invocada em lote pelo Amazon Data Firehose para transformação em voo.
    """
    logger.info(f"Iniciando transformação em lote do Firehose. Total de registros: {len(event.get('records', []))}")
    input_records = event.get("records", [])
    output_records: List[Dict[str, Any]] = []

    # Cache local em memória para reaproveitar buscas do mesmo produto no mesmo lote
    local_product_cache: Dict[str, Any] = {}

    for record in input_records:
        record_id = record.get("recordId")
        raw_data_base64 = record.get("data", "")

        try:
            # 1. Decodificação Base64
            decoded_bytes = base64.b64decode(raw_data_base64)
            decoded_str = decoded_bytes.decode("utf-8").strip()
            payload_dict = json.loads(decoded_str)

            # 2. Processamento e Transformação com Cache do Lote
            result_status, transformed_payload = _transform_single_record(payload_dict, local_product_cache)

            if result_status == "Dropped":
                output_records.append({
                    "recordId": record_id,
                    "result": "Dropped",
                    "data": raw_data_base64
                })
            else:
                # 3. Codificação Base64 do JSON transformado com quebra de linha '\n'
                transformed_json_str = json.dumps(transformed_payload) + "\n"
                # noinspection PyTypeChecker
                encoded_data = base64.b64encode(transformed_json_str.encode("utf-8")).decode("utf-8")

                output_records.append({
                    "recordId": record_id,
                    "result": "Ok",
                    "data": encoded_data
                })

        except Exception:
            logger.exception(f"Erro ao transformar registro Firehose ID: {record_id}. Marcando como ProcessingFailed.")
            output_records.append({
                "recordId": record_id,
                "result": "ProcessingFailed",
                "data": raw_data_base64
            })

    logger.info(f"Transformação de lote Firehose concluída. Total processado: {len(output_records)}")
    return {"records": output_records}