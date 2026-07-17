import os
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_dynamodb_resource = boto3.resource("dynamodb")

class ProductsRepository:
    """
    Classe de Persistência (Data Access Object / Repository) para a tabela de Produtos no DynamoDB.
    Isola o boto3 e os contratos específicos da AWS da lógica de negócios das Lambdas.
    """

    def __init__(self):
        self.table_name = os.environ.get("PRODUCTS_TABLE_NAME")
        if not self.table_name:
            logger.error("A variável de ambiente 'PRODUCTS_TABLE_NAME' não está configurada.")
            raise ValueError("Configuração do sistema inválida: falta nome da tabela.")

        self.table = _dynamodb_resource.Table(self.table_name)

    def get_by_id(self, product_id: str) -> Optional[Dict]:
        """
        [AP_01] Busca um único produto utilizando a Chave de Partição Primária (id).
        Retorna o dicionário de atributos do produto ou None caso não exista.
        """
        try:
            logger.info(f"Buscando produto no DynamoDB com ID: {product_id}")
            response = self.table.get_item(Key={"id": product_id})
            return response.get("Item")
        except ClientError:
            logger.exception(f"Erro ao buscar produto {product_id} no DynamoDB")
            raise

    def save(self, product_data: Dict) -> None:
        """Insere ou substitui completamente um item na tabela do DynamoDB."""
        try:
            logger.info(f"Gravando novo produto no DynamoDB com ID: {product_data.get('id')}")
            self.table.put_item(Item=product_data)
        except ClientError:
            logger.exception("Erro ao persistir produto no DynamoDB")
            raise

    def update(self, product_id: str, product_data: Dict) -> Optional[Dict]:
        """
        Atualiza campos específicos de um produto utilizando expressões de atualização do DynamoDB.
        Evita o risco de concorrência ou de apagar chaves acidentalmente
        """
        try:
            logger.info(f"Atualizando produto {product_id} no DynamoDB.")
            update_parts = []
            expression_attribute_values = {}
            expression_attribute_names = {}

            for key, value in product_data.items():
                placeholder_name = f"#attr_{key}"
                placeholder_val = f":val_{key}"

                update_parts.append(f"{placeholder_name} = {placeholder_val}")
                expression_attribute_names[placeholder_name] = key
                expression_attribute_values[placeholder_val] = value

            if not update_parts:
                return None

            update_expression = "SET " + ", ".join(update_parts)

            response = self.table.update_item(
                Key={"id": product_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            return response.get("Attributes")

        except ClientError:
            logger.exception(f"Erro ao atualizar produto {product_id} no DynamoDB")

    def find_by_category(self, category: str) -> List[Dict]:
        """[AP_02] Realiza uma busca indexada e barata por Categoria utilizando o GSI"""
        try:
            logger.info(f"Buscando produtos no DynamoDB pertencentes à categoria: {category}")
            gsi_name = os.environ.get("CATEGORY_GSI_NAME", "category-index")
            response = self.table.query(
                IndexName=gsi_name,
                KeyConditionExpression="category = :cat_val",
                ExpressionAttributeValues={":cat_val": category}
            )
            return response.get("Items", [])
        except ClientError:
            logger.exception(f"Erro ao buscar produtos da categoria {category} no GSI")
            raise