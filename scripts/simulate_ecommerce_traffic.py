import time
import random
import json
import requests
import boto3

print("🚀 Iniciando Simulação do E-Commerce em Tempo Real com 50 Produtos...")


def get_api_gateway_url() -> str:
    apigw = boto3.client("apigateway", region_name="us-east-1")
    apis = apigw.get_rest_apis()
    for item in apis.get("items", []):
        if item.get("name") == "Products Service":
            return f"https://{item['id']}.execute-api.us-east-1.amazonaws.com/prod"
    raise RuntimeError("API Gateway 'Products Service' não encontrada!")


def get_alb_url() -> str:
    alb_client = boto3.client("elbv2", region_name="us-east-1")
    for alb in alb_client.describe_load_balancers().get("LoadBalancers", []):
        if "Recom" in alb.get("LoadBalancerName", ""):
            return f"http://{alb['DNSName']}"
    raise RuntimeError("Application Load Balancer (ALB) não encontrado!")


API_URL = get_api_gateway_url()
ALB_URL = get_alb_url()
print(f"🔗 API Gateway (Catalogo & Checkout): {API_URL}")
print(f"🔗 Application Load Balancer (Fargate ML): {ALB_URL}")

# ==============================================================================
# ETAPA 1: SEMEAR 50 PRODUTOS DIVERSOS NO CATÁLOGO (POST /products)
# ==============================================================================
print("\n📦 [Passo 1/4] Semeando 50 produtos no catálogo do DynamoDB...")

categories = ["Accessories", "Home", "Computers", "Electronics"]
created_products = []

for i in range(1, 51):
    category = categories[i % len(categories)]

    if category == "Accessories":
        title = f"Equipamento de Combate v{i}"
        description = "Acessório para batalhas e caçadas."
        price = 100.0 + (i * 15.0)
    elif category == "Home":
        title = f"Poção Alquímica Especial v{i}"
        description = "Elixir com propriedades medicinais."
        price = 50.0 + (i * 10.0)
    elif category == "Computers":
        title = f"Teclado/Mouse Gamer v{i}"
        description = "Equipamento periférico tático."
        price = 200.0 + (i * 20.0)
    else:
        title = f"Fone/Headset Eletrônico v{i}"
        description = "Dispositivo eletrônico de áudio."
        price = 150.0 + (i * 12.0)

    prod_payload = {
        "title": title,
        "category": category,
        "description": description,
        "price": round(price, 2),
        "inventory_count": 50
    }

    try:
        res = requests.post(f"{API_URL}/products", json=prod_payload)
        if res.status_code == 201:
            p_data = res.json()
            created_products.append(p_data)
            if i % 10 == 0 or i == 1:
                print(f"  ✅ [Catálogo {i}/50] Cadastrado: '{title}' ({category})")
    except Exception as err:
        print(f"  ❌ Erro ao cadastrar produto {i}: {err}")

# ==============================================================================
# ETAPA 2: CLIENTES NAVEGAM NO CATÁLOGO (GET /products/{id} -> STREAMING FIREHOSE)
# ==============================================================================
print("\n👥 [Passo 2/4] Clientes navegando nos produtos (GET /products/{id})...")

# Geralt navega preferencialmente em Acessórios
accessories_prods = [p for p in created_products if p["category"] == "Accessories"]
home_prods = [p for p in created_products if p["category"] == "Home"]

for i in range(1, 8):
    p = random.choice(accessories_prods)
    requests.get(f"{API_URL}/products/{p['id']}", headers={"X-User-Id": "user_geralt"})
    print(f"  [Geralt Clique {i}/7] Visualizou '{p['title']}' (Accessories)")
    time.sleep(0.1)

# Yennefer navega preferencialmente em Poções/Home
for i in range(1, 8):
    p = random.choice(home_prods)
    requests.get(f"{API_URL}/products/{p['id']}", headers={"X-User-Id": "user_yennefer"})
    print(f"  [Yennefer Clique {i}/7] Visualizou '{p['title']}' (Home)")
    time.sleep(0.1)

# ==============================================================================
# ETAPA 3: CLIENTE EFETUA UMA COMPRA REAL (POST /orders -> EVENTBRIDGE & SQS)
# ==============================================================================
print("\n🛒 [Passo 3/4] CLIENTE COMPRANDO! Realizando Checkout (POST /orders)...")

purchased_product = accessories_prods[0]
order_payload = {
    "customer_id": "user_geralt",
    "customer_email": "geralt@kaermorhen.com",
    "customer_tier": "vip",
    "order_type": "express",
    "total_amount": purchased_product["price"],
    "items": [
        {"product_id": purchased_product["id"], "quantity": 1, "price": purchased_product["price"]}
    ]
}

order_res = requests.post(f"{API_URL}/orders", json=order_payload)
if order_res.status_code == 201:
    o_data = order_res.json()
    print(f"  🎉 COMPRA REALIZADA COM SUCESSO! Order ID: #{o_data['order_id']} (Status: {o_data['status']})")
    print("     ↳ Evento enviado para EventBridge ➔ Fila SQS ➔ Worker ➔ SNS & Firehose Data Lake!")

print("\n⏱️ Aguardando 70 segundos para o buffer do Firehose gravar os arquivos .gz no S3 Data Lake...")
time.sleep(70)

# ==============================================================================
# ETAPA 4: MOTOR FARGATE GERA RECOMENDAÇÕES REAL LENDO O S3 DATA LAKE
# ==============================================================================
print("\n🤖 [Passo 4/4] Consultando Recomendações REAIS do Fargate (Lendo o S3 Data Lake)...")

geralt_res = requests.get(f"{ALB_URL}/recommendations/user_geralt")
if geralt_res.status_code == 200:
    print("\n⚔️ Recomendações Top 5 Calculadas pelo Fargate para 'user_geralt' (Baseadas no Histórico do Data Lake S3):")
    print(json.dumps(geralt_res.json(), indent=2, ensure_ascii=False))

yen_res = requests.get(f"{ALB_URL}/recommendations/user_yennefer")
if yen_res.status_code == 200:
    print("\n🔮 Recomendações Top 5 Calculadas pelo Fargate para 'user_yennefer' (Baseadas no Histórico do Data Lake S3):")
    print(json.dumps(yen_res.json(), indent=2, ensure_ascii=False))

print("\n🎉 Simulação do E-Commerce com Recomendação Real em Fargate Concluída com Sucesso!")