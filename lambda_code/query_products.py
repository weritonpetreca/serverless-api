import json
import logging
from products_db import ProductsRepository
from response_utils import create_success_response, create_error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

repository = ProductsRepository()

def handler(event, context):
    """
    Handler da AWS Lambda responsável por listar produtos de uma determinada categoria.

    Fluxo:
      1. Extrai a categoria dos parâmetros de consulta (queryStringParameters).
      2. Valida a presença do parâmetro obrigatório 'category'.
      3. Executa a busca otimizada via Query no GSI do DynamoDB.
      4. Retorna HTTP 200 (OK) com a lista de produtos (mesmo que vazia []).
    """
    logger.info(f"Iniciando processamento de listagem de produtos por categoria. Evento: {json.dumps(event)}")

    try:
        query_string_parameter = event.get("queryStringParameters") or {}
        category = query_string_parameter.get("category")

        if not category:
            logger.warning("Requisição rejeitada: parâmetro 'category' ausente na queryString.")
            return create_error_response(400, "O parâmetro de busca 'category' é obrigatório na URL.")

        logger.info(f"Buscando produtos pertencentes à categoria: {category}")

        products = repository.find_by_category(category)

        logger.info(f"Busca concluída. Encontrados {len(products)} produtos para a categoria '{category}'")
        return create_success_response(200, products)

    except Exception as e:
        logger.exception(f"Erro imprevisto ao tentar buscar produtos por categoria: {str(e)}")
        return create_error_response(500, "Erro interno do servidor ao processar a consulta por categoria")