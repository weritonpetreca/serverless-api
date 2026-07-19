import json
import logging
from repository.products_db import ProductsRepository
from shared.response_utils import create_success_response
from shared.error_handler import ErrorClassifier, ValidationError

logger = logging.getLogger(__name__)

repository = ProductsRepository()

def handler(event: dict, context) -> dict:
    """
    Handler da AWS Lambda responsável por listar produtos de uma determinada categoria.

    Fluxo:
      1. Extrai a categoria dos parâmetros de consulta (queryStringParameters).
      2. Valida a presença do parâmetro obrigatório 'category'.
      3. Executa a busca otimizada via Query no GSI do DynamoDB.
      4. Retorna HTTP 200 (OK) com a lista de produtos (mesmo que vazia []).
    """
    logger.info(f"Iniciando processamento de listagem de produtos por categoria. Evento: {json.dumps(event)}")
    request_id = context.aws_request_id if context else "fallback-local-id"
    try:
        query_string_parameter = event.get("queryStringParameters") or {}
        category = query_string_parameter.get("category")

        if not category:
            logger.warning("Falha na requisição: parâmetro 'category' ausente na Query String.")
            raise ValidationError("O parâmetro 'category' é obrigatório para esta operação.")

        logger.info(f"Buscando produtos pertencentes à categoria: {category}")
        products = repository.find_by_category(category)

        logger.info(f"Busca concluída. Encontrados {len(products)} produtos para a categoria '{category}'")
        return create_success_response(200, products)

    except ValidationError as e:
        logger.warning(f"Erro de validação na busca por categoria: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)

    except Exception as e:
        logger.exception(f"Erro imprevisto ao tentar buscar produtos por categoria: {str(e)}")
        return ErrorClassifier.handle_exception(e, request_id)