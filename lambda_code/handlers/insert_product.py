import json
import logging
import uuid
from pydantic import ValidationError as PydanticValidationError
from shared.error_handler import ErrorClassifier, ValidationError as DomainValidationError
from shared.config_manager import SSMParameterManager
from shared.response_utils import create_success_response
from repository.products_db import ProductsRepository
from domain.product_schema import ProductInput

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Inicialização dos objetos no escopo global para reaproveitamento em Warm Starts
repository = ProductsRepository()
config_manager = SSMParameterManager(ttl_seconds=300)


def handler(event, context):
    """
    Handler da AWS Lambda responsável pelo cadastro de novos produtos no catálogo (POST /products).
    """
    logger.info(f"Iniciando cadastro de novo produto. Evento: {json.dumps(event)}")
    request_id = context.aws_request_id if context else "fallback-local-id"

    try:
        # Checagem de Feature Flag de manutenção no SSM
        if not config_manager.is_feature_enabled("feature_flag_order_processing"):
            logger.warning("Tentativa de cadastro rejeitada: Catálogo em manutenção via SSM Feature Flag.")
            raise DomainValidationError("Cadastros no catálogo estão temporariamente desativados para manutenção.")

        body_str = event.get("body")
        if not body_str:
            raise DomainValidationError("O corpo da requisição (body) está vazio ou ausente.")

        body_json = json.loads(body_str)

        # Validação do produto com Pydantic v2
        validated_product = ProductInput.model_validate(body_json)

        product_to_save = validated_product.model_dump()
        product_to_save["id"] = str(uuid.uuid4())

        # Persistência síncrona no DynamoDB
        repository.save(product_to_save)

        logger.info(f"Produto cadastrado com sucesso no catálogo! ID gerado: {product_to_save['id']}")
        return create_success_response(201, product_to_save)

    except PydanticValidationError as e:
        logger.warning(f"Falha na validação do produto (Pydantic): {e.errors()}")
        return ErrorClassifier.handle_exception(e, request_id)

    except json.JSONDecodeError:
        logger.warning("Falha ao deserializar o corpo da requisição: JSON inválido.")
        custom_error = DomainValidationError("Formato JSON inválido no corpo da requisição.")
        return ErrorClassifier.handle_exception(custom_error, request_id)

    except DomainValidationError as e:
        logger.warning(f"Falha de validação de negócio: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)

    except Exception as e:
        logger.exception("Erro inesperado durante o cadastro de produto.")
        return ErrorClassifier.handle_exception(e, request_id)