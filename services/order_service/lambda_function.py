def handler(event, context):
    print("Order service received:", event)
    
    return {
        "statusCode": 200
    }