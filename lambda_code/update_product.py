import json
import logging
from pydantic import ValidationError
from products_db import ProductsRepository
from product_schema import ProductUpdateInput
from response_utils import create_success_response, create_error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

repository = ProductsRepository()

def handler(event, context):
    """
    Handler da AWS Lambda responsável por atualizar parcialmente um produto existente.
    Verbo HTTP correspondente: PATCH /products/{id}
    """
    logger.info(f"Iniciando processo de atualização de produto. Evento: {json.dumps(event)}")

    path_parameters = event.get("pathParameters") or {}
    product_id = path_parameters.get("id")

    if not product_id:
        logger.warning("Tentativa de atualização sem fornecer o ID do produto.")
        return create_error_response(400, "O parâmetro 'id' na URL é obrigatório.")

    body_str = event.get("body")
    if not body_str:
        logger.warning(f"Tentativa de atualização com corpo vazio para o produto ID: {product_id}")
        return create_error_response(400, "O corpo da requisição não pode estar vazio.")

    try:
        # Converte a string JSON recebida do API Gateway em dicionário Python
        body_data = json.loads(body_str)

        validated_data = ProductUpdateInput.model_validate(body_data)

        # Filtra apenas os campos que o cliente enviou de fato na requisição (evita sobregravar nulos)
        update_payload = validated_data.model_dump(exclude_unset=True)

        if not update_payload:
            logger.warning(f"Nenhum campo válido enviado para atualização do produto ID: {product_id}")
            return create_error_response(400, "Nenhum campo válido foi fornecido para atualização.")

    except json.JSONDecodeError as e:
        logger.warning(f"Erro ao parsear JSON de entrada: {str(e)}")
        return create_error_response(400, "JSON de entrada mal formatado ou inválido.")
    except ValidationError as e:
        logger.warning(f"Falha de validação de esquema (Pydantic) no PATCH: {e.errors()}")
        error_details = [f"Campo '{err['loc'][0]}': {err['msg']}" for err in e.errors()]
        return create_error_response(400, f"Falha na validação dos dados. Detalhes: {', '.join(error_details)}")

    try:
        existing_product = repository.get_by_id(product_id)
        if not existing_product:
            logger.warning(f"Produto ID: {product_id} não encontrado para atualização.")
            return create_error_response(404, f"Produto com ID '{product_id}' não existe.")

        updated_product = repository.update(product_id, update_payload)

        logger.info(f"Produto ID: {product_id} atualizado com sucesso no DynamoDB.")
        return create_success_response(200, updated_product)

    except Exception as e:
        logger.critical(f"Erro catastrófico ao atualizar produto no DynamoDB: {str(e)}")
        return create_error_response(500, "Erro interno no servidor ao processar a atualização.")