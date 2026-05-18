import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Notification Service
def handler(event, context):
    try:
        record = event.get('Records', [])
        body = json.loads(record[0]['body'])
        detail_type = body['detail-type']
        detail = body['detail']
        order_id = detail['order_id']
        # Ideally send email but printing message here as a simulation
        match detail_type: 
            case 'InventoryReservationFailed':
                item_id = detail['item_id']
                quantity = detail['quantity']
                reason = detail['reason']
                logger.info(f"Your order for {quantity} of {item_id} was not able to be fulfilled due to {reason}.")
            case 'PaymentFailed':
                failure_reason = detail['failure_reason']
                logger.info(f"We failed to finish processing your order due to a payment error: {failure_reason}.")
            case 'PaymentConfirmed':
                logger.info(f"Payment successfully processed for {order_id}")
            case 'OrderShipped':
                logger.info(f"Your order {order_id} has successfully shipped.")
            case 'FulfillmentFailed':
                failure_reason = detail['failure_reason']
                logger.info(f"Your order {order_id} failed to be fulfilled due to {failure_reason}.")
            case _:
                logger.warning("Unknown event type: %s", detail_type)
        
        return {
            "statusCode": 200
        }
    
    except KeyError as e:
        return {
            "statusCode": 400,
            'body': json.dumps({'error': f'Missing required field: {e}'})
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({'error': 'Internal server error'})
        }