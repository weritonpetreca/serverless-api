import json
import logging
from products_db import ProductsRepository
from response_utils import create_success_response, create_error_response
from error_handler import ErrorClassifier, ProductNotFoundError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

repository = ProductsRepository()

def handler(event, context):
    """
    Handler da AWS Lambda responsável por buscar um único produto por ID.

    Fluxo:
      1. Extrai o ID dos parâmetros de rota (pathParameters) fornecidos pelo API Gateway.
      2. Valida se o ID foi enviado corretamente.
      3. Consulta o repositório do DynamoDB.
      4. Se o item não for encontrado, retorna HTTP 404 (Not Found).
      5. Se encontrado, retorna HTTP 200 (OK) com o payload do produto.
    """
    logger.info(f"Iniciando processamento de busca de produto por ID. Evento: {json.dumps(event)}")
    try:
        path_parameters = event.get("pathParameters") or {}
        product_id = path_parameters.get("id")

        if not product_id:
            logger.warning("Requisição rejeitada: ID do produto ausente nos parâmetros de rota.")
            return create_error_response(400, "O parâmetro 'id' do produto é obrigatório no URL.")


        logger.info(f"Buscando informações para o ID do produto: {product_id}")
        product = repository.get_by_id(product_id)

        if not product:
            logger.info(f"Produto com ID {product_id} não foi localizado no banco de dados.")
            return create_error_response(404, f"Produto com ID {product_id} não encontrado.")

        logger.info(f"Produto {product_id} localizado e recuperado com sucesso.")
        return create_success_response(200, product)

    except ProductNotFoundError as e:
        request_id = context.aws_request_id if context else "fallback-local-id"
        logger.warning(f"Produto não localizado: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)

    except Exception as e:
        request_id = context.aws_request_id if context else "fallback-local-id"
        logger.exception(f"Erro imprevisto ao tentar buscar o produto: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)