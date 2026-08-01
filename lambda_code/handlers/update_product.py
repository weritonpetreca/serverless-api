import json
import logging
from pydantic import ValidationError
from repository.products_db import ProductsRepository
from domain.product_schema import ProductUpdateInput
from shared.config_manager import SSMParameterManager
from shared.error_handler import ErrorClassifier, ProductNotFoundError, ValidationError as DomainValidationError
from shared.response_utils import create_success_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicialização dos objetos no escopo global para reaproveitamento em Warm Starts
repository = ProductsRepository()
config_manager = SSMParameterManager(ttl_seconds=300)


def handler(event, context):
    """
    Handler da AWS Lambda responsável por atualizar parcialmente um produto existente.
    Verbo HTTP correspondente: PATCH /products/{id}
    """
    logger.info(f"Iniciando processo de atualização de produto. Evento: {json.dumps(event)}")
    request_id = context.aws_request_id if context else "fallback-local-id"
    product_id = "desconhecido"

    try:
        path_parameters = event.get("pathParameters") or {}
        product_id = path_parameters.get("id")

        if not product_id:
            logger.warning("Tentativa de atualização sem fornecer o ID do produto.")
            raise DomainValidationError("O parâmetro 'id' na URL é obrigatório.")

        # 1. Validação de Feature Flag via AWS SSM Parameter Store (Dynamic Control)
        if not config_manager.is_feature_enabled("feature_flag_image_processing"):
            logger.warning(f"Tentativa de atualização rejeitada para produto ID {product_id}: Operações desativadas via SSM Feature Flag.")
            raise DomainValidationError("Atualizações no catálogo estão temporariamente desativadas para manutenção.")

        body_str = event.get("body")
        if not body_str:
            logger.warning(f"Tentativa de atualização com corpo vazio para o produto ID: {product_id}")
            raise DomainValidationError("O corpo da requisição não pode estar vazio.")

        body_data = json.loads(body_str)
        validated_data = ProductUpdateInput.model_validate(body_data)

        update_payload = validated_data.model_dump(exclude_unset=True)

        if not update_payload:
            logger.warning(f"Nenhum campo válido enviado para atualização do produto ID: {product_id}")
            raise DomainValidationError("Nenhum campo válido foi fornecido para atualização.")

        existing_product = repository.get_by_id(product_id)
        if not existing_product:
            logger.warning(f"Produto ID: {product_id} não encontrado para atualização.")
            raise ProductNotFoundError(f"Produto com ID '{product_id}' não existe.")

        updated_product = repository.update(product_id, update_payload)

        logger.info(f"Produto ID: {product_id} atualizado com sucesso no DynamoDB.")
        return create_success_response(200, updated_product)

    except (ValidationError, DomainValidationError, ProductNotFoundError) as e:
        return ErrorClassifier.handle_exception(e, request_id)

    except json.JSONDecodeError as e:
        logger.warning(f"Erro ao parsear JSON de entrada: {str(e)}")
        custom_error = DomainValidationError("JSON de entrada mal formatado ou inválido.")
        return ErrorClassifier.handle_exception(custom_error, request_id)

    except Exception as e:
        # SonarQube S8572: Registro do traceback completo no CloudWatch Logs via logger.exception
        logger.exception(f"Erro catastrófico ao atualizar produto ID {product_id} no DynamoDB.")
        return ErrorClassifier.handle_exception(e, request_id)