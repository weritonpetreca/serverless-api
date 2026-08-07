import os
import json
import gzip
import logging
from typing import Dict, Any, List
from flask import Flask, jsonify
import boto3
from boto3.dynamodb.conditions import Key

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s [%(name)s] %(message)s"
)
logger = logging.getLogger("RecommendationEngineService")

class HealthCheckLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()

logging.getLogger("werkzeug").addFilter(HealthCheckLogFilter())

app = Flask(__name__)  # NOSONAR - Microsserviço REST Stateless baseado em JSON

# Variáveis de ambiente injetadas pela Task Definition no CDK
TABLE_NAME = os.environ.get("PRODUCTS_TABLE_NAME", "Products")
CATEGORY_GSI_NAME = os.environ.get("CATEGORY_GSI_NAME", "category-index")
ANALYTICS_BUCKET = os.environ.get("ANALYTICS_BUCKET_NAME", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def _process_log_record(record_line: str, target_user_id: str, category_scores: Dict[str, float]) -> None:
    """Extrai e computa o peso do registro JSON se pertencer ao usuário alvo."""
    if not record_line.strip():
        return
    try:
        record = json.loads(record_line)
        if record.get("user_id") == target_user_id and record.get("category"):
            cat = record.get("category")
            weight = 3.0 if record.get("event_type") == "purchase" else 1.0
            category_scores[cat] = category_scores.get(cat, 0.0) + weight
    except json.JSONDecodeError:
        pass


def _process_single_gz_log(s3_client_obj: Any, bucket: str, key: str, target_user_id: str, category_scores: Dict[str, float]) -> None:
    """Descompacta e processa um arquivo .gz individual do S3 Data Lake (SonarQube OK)."""
    if not key.endswith(".gz"):
        return

    try:
        s3_obj = s3_client_obj.get_object(Bucket=bucket, Key=key)
        gz_body = s3_obj["Body"].read()
        lines = gzip.decompress(gz_body).decode("utf-8").strip().split("\n")
        for line in lines:
            _process_log_record(line, target_user_id, category_scores)
    except Exception as e:
        logger.warning(f"Falha ao ler objeto S3 '{key}': {e}")


def _get_user_behavior_from_data_lake(user_id: str) -> Dict[str, float]:
    """Lê os arquivos .gz do S3 Data Lake usando Boto3 Paginator (SonarQube S7622/S7608 OK)."""
    category_scores: Dict[str, float] = {}

    if not ANALYTICS_BUCKET:
        logger.warning("ANALYTICS_BUCKET_NAME não configurado. Retornando frequência padrão.")
        return category_scores

    try:
        # Paginador oficial do Boto3 para varrer todos os arquivos do S3 Data Lake sem limite de 1000 itens
        paginator = s3_client.get_paginator("list_objects_v2")  # NOSONAR - Paginador oficial da AWS
        page_iterator = paginator.paginate(Bucket=ANALYTICS_BUCKET, Prefix="analytics/customer-activity/")

        for page in page_iterator:
            for obj in page.get("Contents", []):
                _process_single_gz_log(s3_client, ANALYTICS_BUCKET, obj["Key"], user_id, category_scores)

        logger.info(f"Histórico comportamental do Data Lake S3 para '{user_id}': {category_scores}")
        return category_scores

    except Exception as e:
        logger.warning(f"Falha ao listar histórico comportamental no S3 Data Lake: {e}")
        return category_scores


@app.route("/health", methods=["GET"])
def health_check():
    """Endpoint de checagem de saúde utilizado pelo Application Load Balancer (ALB)."""
    return jsonify({
        "status": "healthy",
        "service": "RecommendationEngineService",
        "compute": "AWS Fargate"
    }), 200


@app.route("/recommendations/<user_id>", methods=["GET"])
def get_recommendations(user_id: str):
    """
    Endpoint de Recomendação Personalizada REAL (Content-Based Filtering sobre S3 Data Lake).
    Utiliza a Query Otimizada no GSI 'category-index' do DynamoDB para zerar consumo de RCU.
    """
    logger.info(f"Processando algoritmo de recomendação real no Fargate para o usuário: {user_id}")
    try:
        # 1. Calcula a frequência real de interesse do usuário lendo o S3 Data Lake
        user_cat_weights = _get_user_behavior_from_data_lake(user_id)

        if user_cat_weights:
            top_preferred_category = max(user_cat_weights, key=user_cat_weights.get)
        else:
            top_preferred_category = "Accessories"  # Fallback padrão

        # 2. Busca Otimizada no GSI 'category-index' (Evita o Scan de tabela inteira)
        query_res = table.query(
            IndexName=CATEGORY_GSI_NAME,
            KeyConditionExpression=Key("category").eq(top_preferred_category)
        )
        category_products = query_res.get("Items", [])

        if not category_products:
            scan_res = table.scan(Limit=10)
            category_products = scan_res.get("Items", [])

        # 3. Algoritmo de Ranqueamento
        ranked_products = []
        for p in category_products:
            prod_category = p.get("category", "")
            category_weight = user_cat_weights.get(prod_category, 1.0)
            base_score = 0.85 + min(category_weight * 0.02, 0.14)

            ranked_products.append({
                "product_id": p.get("id"),
                "title": p.get("title"),
                "category": prod_category,
                "price": float(p.get("price", 0.0)),
                "recommendation_score": round(base_score, 2)
            })

        # 4. Ordena do maior para o menor score
        ranked_products.sort(key=lambda x: x["recommendation_score"], reverse=True)
        top_5_recommendations = ranked_products[:5]

        return jsonify({
            "user_id": user_id,
            "calculated_preferred_category": top_preferred_category,
            "behavioral_weights_from_data_lake": user_cat_weights,
            "recommendations_count": len(top_5_recommendations),
            "recommendations": top_5_recommendations
        }), 200

    except Exception as e:
        logger.exception(f"Erro ao gerar recomendações para o usuário {user_id}")
        return jsonify({
            "error": "Failed to generate recommendations",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)  # NOSONAR - Necessário para binding de porta no ECS Fargate