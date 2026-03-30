def handler(event, context):
    print("Payment received:", event)
    
    return {
        "statusCode": 200
    }