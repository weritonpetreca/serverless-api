import json

def handler(event, context):
    products = [
        {"id": "prod_001", "name": "Laptop Gamer", "price": 4500.00, "category": "Electronics"},
        {"id": "prod_002", "name": "Teclado Gamer", "price": 350.00, "category": "Electronics"},
        {"id": "prod_003", "name": "Caneca Dev", "price": 45.00, "category": "Office"},
    ]

    query_params = event.get('queryStringParameters') or {}
    category_filter = query_params.get('category')

    if category_filter:
        products = [p for p in products if p['category'].lower() == category_filter.lower()]

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(products)
    }