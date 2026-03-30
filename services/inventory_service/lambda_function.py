def handler(event, context):
    print("Inventory service received:", event)
    
    return {
        "statusCode": 200
    }