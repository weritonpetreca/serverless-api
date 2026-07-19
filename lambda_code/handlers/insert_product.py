import json
import logging
import uuid
from pydantic import ValidationError as PydanticValidationError
from shared.error_handler import ErrorClassifier, ValidationError as DomainValidationError
from repository.products_db import ProductsRepository
from domain.product_schema import ProductInput
from shared.response_utils import create_success_response

logger = logging.getLogger(__name__)

repository = ProductsRepository()

def handler(event, context):
    """
    Handler da AWS Lambda responsável pela criação de novos produtos.

    Fluxo:
      1. Extrai o corpo da requisição HTTP (JSON).
      2. Valida o payload contra o schema do Pydantic v2.
      3. Se inválido, retorna 400 (Bad Request) com detalhes claros do erro.
      4. Se válido, injeta um ID seguro (UUID v4) e persiste no DynamoDB.
      5. Retorna 201 (Created) com os dados do produto salvo.
    """
    logger.info(f"Iniciando processamento da requisição de cadastro de produto. Evento: {json.dumps(event)}")
    request_id = context.aws_request_id if context else "falback-local-id"

    try:
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

    except json.JSONDecodeError as e:
        request_id = context.aws_request_id if context else "fallback-local-id"
        logger.warning("Falha ao deserializar o corpo da requisição: JSON inválido de sintaxe.")
        custom_error = DomainValidationError("Formato JSON inválido no corpo da requisição.")
        return ErrorClassifier.handle_exception(custom_error, request_id)

    except DomainValidationError as e:
        logger.warning(f"Falha de validação de negócio: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)

    except Exception as e:
        request_id = context.aws_request_id if context else "fallback-local-id"
        logger.exception("Erro inesperado e não tratado durante a execução do Lambda.")
        return ErrorClassifier.handle_exception(e, request_id)