import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

from domain.product_schema import PresignedUrlResponse
from shared.config_manager import SSMParameterManager
from shared.error_handler import ErrorClassifier, ValidationError as DomainValidationError
from shared.response_utils import create_success_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicialização dos clientes Boto3 e Gerenciadores no escopo global (Warm Start)
s3_client = boto3.client("s3")
config_manager = SSMParameterManager(ttl_seconds=300)

# Mapeamento de MIME types permitidos para extensões de arquivo (DevSecOps Hardening)
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp"
}


def handler(event, context):
    """
    Handler da AWS Lambda responsável por gerar URLs pré-assinadas do S3 para upload direto de mídias.
    Verbo HTTP correspondente: POST /products/{id}/upload-url
    """
    logger.info(f"Iniciando requisição de URL pré-assinada para upload S3. Evento: {json.dumps(event)}")
    request_id = context.aws_request_id if context else "fallback-local-id"

    try:
        bucket_name = os.environ.get("PRODUCT_IMAGE_BUCKET")
        if not bucket_name:
            logger.error("Variável de ambiente PRODUCT_IMAGE_BUCKET não foi encontrada.")
            raise RuntimeError("Configuração de armazenamento de imagens no S3 ausente.")

        path_parameters = event.get("pathParameters") or {}
        product_id = path_parameters.get("id")

        if not product_id:
            logger.warning("Solicitação de upload de imagem sem fornecer o ID do produto.")
            raise DomainValidationError("O parâmetro 'id' do produto é obrigatório na URL.")

        query_params = event.get("queryStringParameters") or {}
        image_type = query_params.get("type", "main")
        content_type = query_params.get("content_type", "image/jpeg").lower()

        if content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"Tentativa de upload com Content-Type não suportado: {content_type}")
            raise DomainValidationError(
                f"Tipo de conteúdo '{content_type}' não suportado. "
                f"Tipos permitidos: {list(ALLOWED_CONTENT_TYPES.keys())}"
            )

        # 🚀 LEITURA DINÂMICA DO TIMEOUT/EXPIRAÇÃO VIA AWS SSM PARAMETER STORE
        raw_timeout = config_manager.get_parameter("api_timeout", default_value="3600")
        try:
            expires_in = int(raw_timeout)
        except ValueError:
            expires_in = 3600

        extension = ALLOWED_CONTENT_TYPES[content_type]
        object_key = f"products/{product_id}/{image_type}{extension}"

        # Gera a URL Pré-assinada limitando o ContentType e usando a expiração dinâmica do SSM
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": object_key,
                "ContentType": content_type
            },
            ExpiresIn=expires_in
        )

        response_data = PresignedUrlResponse(
            upload_url=presigned_url,
            object_key=object_key,
            expires_in=expires_in
        )

        logger.info(f"Presigned URL para upload gerada com sucesso para a chave: {object_key} (Expira em: {expires_in}s)")
        return create_success_response(200, response_data.model_dump())

    except (DomainValidationError,) as e:
        return ErrorClassifier.handle_exception(e, request_id)

    except Exception as e:
        # SonarQube S8572: Registro completo do traceback no CloudWatch Logs
        logger.exception("Erro catastrófico ao gerar Presigned URL no S3.")
        return ErrorClassifier.handle_exception(e, request_id)