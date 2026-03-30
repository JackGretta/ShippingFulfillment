def handler(event, context):
    print("Fulfillment service received:", event)
    
    return {
        "statusCode": 200
    }