import json
import logging
import uuid
from pydantic import ValidationError
from products_db import ProductsRepository
from product_schema import ProductInput
from response_utils import create_success_response, create_error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

    try:
        body_str = event.get("body")
        if not body_str:
            return create_error_response(400, "O corpo da requisição (body) está vazio ou ausente.")

        body_json = json.loads(body_str)

        validated_product = ProductInput.model_validate(body_json)

        product_to_save = validated_product.model_dump()
        product_to_save["id"] = str(uuid.uuid4())

        repository.save(product_to_save)

        logger.info(f"Produto persistido com sucesso! ID gerado: {product_to_save['id']}")
        return create_success_response(201, product_to_save)

    except ValidationError as e:
        logger.warning(f"Falha na validação dos dados de entrada: {e.errors()}")

        error_details = [f"Campo '{err['loc'][0]}': {err['msg']}" for err in e.errors()]
        return create_error_response(400, f"Dados inválidos: {', '.join(error_details)}")

    except json.JSONDecodeError:
        logger.warning("Falha ao deserializar o corpo da requisição: JSON inválido.")
        return create_error_response(400, "Formato JSON inválido no corpo da requisição.")

    except Exception as e:
        logger.exception(f"Erro inesperado e não tratado durante a execução do Lambda: {str(e)}")
        return create_error_response(500, "Erro interno do servidor ao processar a requisição")