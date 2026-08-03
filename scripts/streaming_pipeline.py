import time
import random
import json
import requests
import boto3

def get_api_url() -> str:
    """Busca dinamicamente a URL do API Gateway na AWS."""
    apigw = boto3.client("apigateway", region_name="us-east-1")
    apis = apigw.get_rest_apis()
    for item in apis.get("items", []):
        if item.get("name") == "Products Service":
            api_id = item["id"]
            return f"https://{api_id}.execute-api.us-east-1.amazonaws.com/prod"
    raise RuntimeError("API Gateway não encontrada!")

API_URL = get_api_url()
print(f"🔗 URL do API Gateway: {API_URL}")

# 1. Cadastrar um produto válido
product_payload = {
    "title": "Teclado Mecânico RGB",
    "category": "Computers",
    "description": "Teclado mecânico RGB.",
    "price": 350.00
}

res = requests.post(f"{API_URL}/products", json=product_payload)
if res.status_code == 201:
    product_id = res.json()["id"]
    print(f"✅ [CAMINHO 1 - Ok] Produto cadastrado ID: {product_id}")
else:
    print(f"❌ Falha no cadastro do produto: {res.text}")
    exit(1)

# 2. Gerar 5 eventos reais (result: 'Ok' ➔ Vão para analytics/)
print("\n🌊 Gerando 5 eventos de usuários reais (result: 'Ok' ➔ analytics/)...")
for i in range(1, 6):
    user_id = f"user_{random.randint(100, 999)}"
    requests.get(f"{API_URL}/products/{product_id}", headers={"X-User-Id": user_id})
    print(f"  [Ok] GET /products/{product_id} (Usuário: {user_id})")

# 3. Gerar 2 eventos de bots (result: 'Dropped' ➔ Descartados na memória, 0 bytes no S3)
print("\n🤖 Gerando 2 eventos de robôs (result: 'Dropped' ➔ Descartados em voo)...")
requests.get(f"{API_URL}/products/{product_id}", headers={"X-User-Id": "test_bot_111"})
requests.get(f"{API_URL}/products/{product_id}", headers={"X-User-Id": "test_bot_222"})

# 4. Injetar 1 evento corrompido direto no Firehose (result: 'ProcessingFailed' ➔ Vai para errors/)
print("\n💥 Injetando 1 evento corrompido não-JSON direto no Firehose (result: 'ProcessingFailed' ➔ errors/)...")
firehose_client = boto3.client("firehose", region_name="us-east-1")
corrupted_payload = "STRING_CORROMPIDA_SEM_SINTAXE_JSON\n"

firehose_client.put_record(
    DeliveryStreamName="customer-activity-stream",
    Record={"Data": corrupted_payload.encode("utf-8")}
)
print("  [ProcessingFailed] Registro corrompido injetado no Firehose!")

print("\n✨ Teste dos 3 caminhos concluído!")
print("⏱️ Aguarde 60 segundos para o buffer do Firehose descarregar as duas pastas no S3:")
print("   -analytics/customer-activity/ (com os eventos reais)")
print("   -errors/firehose/processing-failed/ (com o evento corrompido)")