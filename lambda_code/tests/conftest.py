import os

# ==============================================================================
# 🌌 CONFIGURAÇÃO DO AMBIENTE DE TESTES (MOCK ENVIRONMENT)
# ==============================================================================
# Define as variáveis de ambiente necessárias para que a inicialização global
# do boto3/repositório não quebre durante a execução dos testes unitários locais.
os.environ["PRODUCTS_TABLE_NAME"] = "MockProductsTable"
os.environ["CATEGORY_GSI_NAME"] = "category-index"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"