import json

def handler(event, context):
    products = {
        "prod_001": {"id": "prod_001", "name": "Laptop Gamer", "price": 4500.00, "category": "Electronics"},
        "prod_002": {"id": "prod_002", "name": "Teclado Mecânico", "price": 350.00, "category": "Electronics"},
        "prod_003": {"id": "prod_003", "name": "Caneca Dev", "price": 45.00, "category": "Office"}
    }

    path_parameters = event.get('pathParameters') or {}
    product_id = path_parameters.get('id')

    product = products.get(product_id)

    if not product:
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Product not found'})
        }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(product)
    }