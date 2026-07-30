import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from domain.product_schema import ProductImageMetadata
from repository.products_db import ProductsRepository

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicialização dos clientes Boto3 no escopo global (Warm Start)
s3_client = boto3.client("s3")
repository = ProductsRepository()


def _process_s3_record(record: Dict[str, Any], bucket_owner_id: Optional[str]) -> Optional[Dict[str, str]]:
    """
    Função auxiliar responsável por processar um único registro de evento do S3.
    Reduz a complexidade cognitiva da função principal 'handler'.
    """
    s3_data = record.get("s3", {})
    bucket_name = s3_data.get("bucket", {}).get("name")
    object_key = s3_data.get("object", {}).get("key", "unknown")

    if not bucket_name or object_key == "unknown":
        logger.warning(f"Registro de evento S3 malformado ignorado: {record}")
        return None

    logger.info(f"Processando metadados do arquivo no S3. Bucket: {bucket_name}, Chave: {object_key}")

    # Validação da convenção de chave: products/{product_id}/{image_type}.ext
    key_parts = object_key.split("/")
    if len(key_parts) < 3 or key_parts[0] != "products":
        logger.warning(f"Chave S3 fora do padrão do catálogo ignorada: {object_key}")
        return None

    product_id = key_parts[1]

    # Parâmetros para validação de proprietário do bucket S3 (DevSecOps)
    head_params: Dict[str, Any] = {"Bucket": bucket_name, "Key": object_key}
    if bucket_owner_id:
        head_params["ExpectedBucketOwner"] = bucket_owner_id

    try:
        # Obtenção dos metadados do arquivo no S3
        head_response = s3_client.head_object(**head_params)
        file_size_bytes = head_response.get("ContentLength", 0)
        last_modified = head_response.get("LastModified")

        upload_date_iso = (
            last_modified.isoformat() if hasattr(last_modified, "isoformat")
            else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        region = os.environ.get("AWS_REGION", "us-east-1")
        image_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_key}"

        metadata_model = ProductImageMetadata(
            image_url=image_url,
            object_key=object_key,
            file_size_bytes=file_size_bytes,
            upload_date=upload_date_iso
        )

        # Atualização no DynamoDB e invalidação de cache
        repository.add_image_to_product(
            product_id=product_id,
            image_url=image_url,
            metadata=metadata_model.model_dump()
        )

        logger.info(f"Metadados de imagem associados com sucesso ao produto ID: {product_id}")
        return {"product_id": product_id, "object_key": object_key}

    except ClientError:
        logger.exception(f"Erro no SDK Boto3 S3 ao consultar head_object para a chave: {object_key}")
        raise

    except Exception:
        logger.exception(f"Erro inesperado ao processar evento S3 para a chave: {object_key}")
        raise


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler da AWS Lambda reativa acionada assincronamente por eventos do Amazon S3 (s3:ObjectCreated:*).
    """
    logger.info(f"Iniciando processamento de evento S3. Evento: {json.dumps(event)}")

    records = event.get("Records") or []
    if not records:
        logger.warning("Nenhum registro 'Records' encontrado no evento do S3.")
        return {"statusCode": 200, "body": json.dumps({"message": "Nenhum evento para processar."})}

    processed_items = []
    bucket_owner_id = os.environ.get("AWS_ACCOUNT_ID")

    for record in records:
        result = _process_s3_record(record, bucket_owner_id)
        if result:
            processed_items.append(result)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Eventos S3 processados com sucesso.",
            "processed_items": processed_items
        })
    }