def handler(event, context):
    print("Notification service received:", event)
    
    return {
        "statusCode": 200
    }