import os
import logging
from typing import Dict, List, Optional, Any
import boto3
from botocore.exceptions import ClientError
from shared.error_handler import RetryableError, InsufficientStockError, ProductNotFoundError
from shared.resilience import retry_with_backoff
from shared.config_manager import SSMParameterManager
from repository.cache_db import CacheRepository

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_dynamodb_resource = boto3.resource("dynamodb")


class ProductsRepository:
    """
    Classe de Persistência (Data Access Object / Repository) para a tabela de Produtos no DynamoDB.
    Aplica o padrão Cache-Aside (Lazy Loading) com ElastiCache e governança de configurações dinâmicas via SSM Parameter Store.
    """

    def __init__(self) -> None:
        self.table_name = os.environ.get("PRODUCTS_TABLE_NAME")
        if not self.table_name:
            logger.error("A variável de ambiente 'PRODUCTS_TABLE_NAME' não está configurada.")
            raise ValueError("Configuração do sistema inválida: falta nome da tabela.")

        self.table = _dynamodb_resource.Table(self.table_name)
        self.cache = CacheRepository()
        self.config = SSMParameterManager(ttl_seconds=300)

    def _classify_and_raise_error(self, error: ClientError, context_message: str) -> None:
        """
        Método privado utilitário para interceptar códigos AWS
        e decidir se a falha merece um Retry.
        """
        error_code = error.response["Error"]["Code"]
        error_message = error.response["Error"]["Message"]

        logger.error(f"{context_message} | AWS Code: {error_code} | Message: {error_message}")

        retryable_codes = {
            "ProvisionedThroughputExceededException",
            "ThrottlingException",
            "InternalServerError"
        }

        if error_code in retryable_codes:
            raise RetryableError(f"Instabilidade temporária na AWS: {error_message}")

        raise error

    @retry_with_backoff(max_attempts=3, base_delay=0.2)
    def get_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        [AP_01] Busca um produto utilizando a Chave Primária (id).
        Aplica o padrão Cache-Aside: consulta o ElastiCache antes de ir ao DynamoDB.
        Lê o TTL de cache dinamicamente a partir do AWS SSM Parameter Store.
        """
        cache_key = f"product:{product_id}"
        cached_product = self.cache.get_json(cache_key)
        if cached_product is not None:
            return cached_product

        try:
            logger.info(f"Buscando produto no DynamoDB com ID: {product_id}")
            response = self.table.get_item(Key={"id": product_id})
            item = response.get("Item")

            if item:
                raw_ttl = self.config.get_parameter("cache_ttl_product", default_value="3600")
                try:
                    ttl_seconds = int(raw_ttl)
                except ValueError:
                    ttl_seconds = 3600

                self.cache.set_json(cache_key, item, ttl_seconds=ttl_seconds)

            return item

        except ClientError as e:
            self._classify_and_raise_error(e, f"Erro ao buscar produto {product_id} no DynamoDB")
            return None

    @retry_with_backoff(max_attempts=3, base_delay=0.2)
    def save(self, product_data: Dict[str, Any]) -> None:
        """
        Insere um novo item na tabela do DynamoDB e invalida o cache do produto e da categoria.
        """
        try:
            product_id = product_data.get('id')
            logger.info(f"Gravando novo produto no DynamoDB com ID: {product_id}")
            self.table.put_item(Item=product_data)

            if product_id:
                self.cache.delete(f"product:{product_id}")
            category = product_data.get("category")
            if category:
                self.cache.delete(f"search:category:{category}")

        except ClientError as e:
            self._classify_and_raise_error(e, "Erro ao persistir produto no DynamoDB")

    @retry_with_backoff(max_attempts=3, base_delay=0.2)
    def update(self, product_id: str, product_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Atualiza campos específicos de um produto utilizando expressões de atualização do DynamoDB.
        Invalida as chaves de cache afetadas pela alteração.
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

            updated_attributes = response.get("Attributes")

            self.cache.delete(f"product:{product_id}")
            category = product_data.get("category")
            if category:
                self.cache.delete(f"search:category:{category}")

            return updated_attributes

        except ClientError as e:
            self._classify_and_raise_error(e, f"Erro ao atualizar produto {product_id} no DynamoDB")
            return None

    @retry_with_backoff(max_attempts=3, base_delay=0.2)
    def find_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        [AP_02] Realiza uma busca por Categoria com Cache-Aside e consulta ao GSI do DynamoDB.
        Lê o TTL de cache dinamicamente a partir do AWS SSM Parameter Store.
        """
        cache_key = f"search:category:{category}"
        cached_list = self.cache.get_json(cache_key)
        if cached_list is not None:
            return cached_list

        try:
            logger.info(f"Buscando produtos no DynamoDB pertencentes à categoria: {category}")
            gsi_name = os.environ.get("CATEGORY_GSI_NAME", "category-index")
            response = self.table.query(
                IndexName=gsi_name,
                KeyConditionExpression="category = :cat_val",
                ExpressionAttributeValues={":cat_val": category}
            )
            items = response.get("Items", [])

            raw_ttl = self.config.get_parameter("cache_ttl_category", default_value="1800")
            try:
                ttl_seconds = int(raw_ttl)
            except ValueError:
                ttl_seconds = 1800

            self.cache.set_json(cache_key, items, ttl_seconds=ttl_seconds)

            return items

        except ClientError as e:
            self._classify_and_raise_error(e, f"Erro ao buscar produtos da categoria {category} no GSI")
            return []

    @retry_with_backoff(max_attempts=3, base_delay=0.2)
    def reserve_stock(self, product_id: str, quantity: int) -> Dict[str, Any]:
        """
        Executa a reserva atômica de estoque no DynamoDB.
        Garante que inventory_count >= quantity antes de decrementar (Zero Race Conditions).
        Lança InsufficientStockError se o estoque for insuficiente.
        """
        try:
            logger.info(f"Tentando reserva atômica de {quantity} unidade(s) do produto: {product_id}")
            response = self.table.update_item(
                Key={"id": product_id},
                UpdateExpression="SET inventory_count = inventory_count - :qty",
                ConditionExpression="attribute_exists(id) AND inventory_count >= :qty",
                ExpressionAttributeValues={":qty": quantity},
                ReturnValues="UPDATED_NEW"
            )

            updated_attributes = response.get("Attributes", {})
            remaining_inventory = int(updated_attributes.get("inventory_count", 0))

            self.cache.delete(f"product:{product_id}")

            if remaining_inventory <= 3:
                logger.warning(
                    f"🚨 [LOW STOCK ALERT] Estoque crítico para o produto ID '{product_id}'! "
                    f"Restante: {remaining_inventory} unidade(s)."
                )

            return {"success": True, "remaining_inventory": remaining_inventory}

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConditionalCheckFailedException":
                product = self.get_by_id(product_id)
                if not product:
                    raise ProductNotFoundError(f"Produto ID '{product_id}' não encontrado no catálogo.")

                curr_stock = int(product.get("inventory_count", 0))
                raise InsufficientStockError(
                    f"Estoque insuficiente para o produto '{product.get('title')}'. "
                    f"Solicitado: {quantity}, Disponível em estoque: {curr_stock}"
                )

            self._classify_and_raise_error(e, f"Erro ao reservar estoque do produto {product_id} no DynamoDB")
            return {"success": False, "remaining_inventory": 0}

    @retry_with_backoff(max_attempts=3, base_delay=0.2)
    def release_stock(self, product_id: str, quantity: int) -> None:
        """
        Executa o incremento atômico de estoque no DynamoDB para o Saga Pattern (Estorno Compensatório).
        """
        try:
            logger.info(f"Devolvendo {quantity} unidade(s) ao estoque do produto: {product_id}")
            self.table.update_item(
                Key={"id": product_id},
                UpdateExpression="SET inventory_count = inventory_count + :qty",
                ConditionExpression="attribute_exists(id)",
                ExpressionAttributeValues={":qty": quantity}
            )
            self.cache.delete(f"product:{product_id}")
            logger.info(f"🔄 [SAGA ROLLBACK] Estoque devolvido (+{quantity}) para o produto ID: {product_id}")

        except ClientError as e:
            logger.exception(f"Falha não-bloqueante ao estornar estoque do produto ID: {product_id}")

    @retry_with_backoff(max_attempts=3, base_delay=0.2)
    def add_image_to_product(self, product_id: str, image_url: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Associa a URL e os metadados de uma imagem ao produto no DynamoDB e invalida o cache.
        """
        try:
            logger.info(f"Anexando imagem e metadados ao produto {product_id} no DynamoDB.")

            update_expression = (
                "SET image_urls = list_append(if_not_exists(image_urls, :empty_list), :new_url_list), "
                "images_metadata = list_append(if_not_exists(images_metadata, :empty_list), :new_meta_list)"
            )

            expression_attribute_values = {
                ":empty_list": [],
                ":new_url_list": [image_url],
                ":new_meta_list": [metadata]
            }

            response = self.table.update_item(
                Key={"id": product_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )

            updated_attributes = response.get("Attributes", {})

            self.cache.delete(f"product:{product_id}")

            return updated_attributes

        except ClientError as e:
            self._classify_and_raise_error(e, f"Erro ao anexar metadados da imagem ao produto {product_id} no DynamoDB")
            return {}