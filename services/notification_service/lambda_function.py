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
                items = detail['items']                
                reason = detail['reason']
                item_desc = ", ".join(f"{i['quantity']} of {i['item_id']}" for i in items)
                logger.info(f"Your order for {item_desc} was not able to be fulfilled due to {reason}.")
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
        logger.error(f"Missing required field: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise