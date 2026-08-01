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
    Handler da AWS Lambda responsável pela criação de novos produtos.

    Fluxo:
      1. Verifica Feature Flag no SSM Parameter Store para autorizar novos cadastros.
      2. Extrai o corpo da requisição HTTP (JSON).
      3. Valida o payload contra o schema do Pydantic v2.
      4. Se inválido, retorna 400 (Bad Request) com detalhes claros do erro.
      5. Se válido, injeta um ID seguro (UUID v4) e persiste no DynamoDB.
      6. Retorna 201 (Created) com os dados do produto salvo.
    """
    logger.info(f"Iniciando processamento da requisição de cadastro de produto. Evento: {json.dumps(event)}")
    request_id = context.aws_request_id if context else "fallback-local-id"

    try:
        # 1. Validação de Feature Flag via AWS SSM Parameter Store (Dynamic Control)
        if not config_manager.is_feature_enabled("feature_flag_image_processing"):
            logger.warning("Tentativa de cadastro rejeitada: Operações do catálogo desativadas via SSM Feature Flag.")
            raise DomainValidationError("Cadastros no catálogo estão temporariamente desativados para manutenção.")

        body_str = event.get("body")
        if not body_str:
            raise DomainValidationError("O corpo da requisição (body) está vazio ou ausente.")

        body_json = json.loads(body_str)

        validated_product = ProductInput.model_validate(body_json)

        product_to_save = validated_product.model_dump()
        product_to_save["id"] = str(uuid.uuid4())

        repository.save(product_to_save)

        logger.info(f"Produto persistido com sucesso! ID gerado: {product_to_save['id']}")
        return create_success_response(201, product_to_save)

    except PydanticValidationError as e:
        logger.warning(f"Falha na validação dos dados de entrada (Pydantic): {e.errors()}")
        return ErrorClassifier.handle_exception(e, request_id)

    except json.JSONDecodeError:
        logger.warning("Falha ao deserializar o corpo da requisição: JSON inválido de sintaxe.")
        custom_error = DomainValidationError("Formato JSON inválido no corpo da requisição.")
        return ErrorClassifier.handle_exception(custom_error, request_id)

    except DomainValidationError as e:
        logger.warning(f"Falha de validação de negócio: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)

    except Exception as e:
        logger.exception("Erro inesperado e não tratado durante a execução da Lambda.")
        return ErrorClassifier.handle_exception(e, request_id)