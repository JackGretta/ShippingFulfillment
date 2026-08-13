from datetime import datetime, timezone
import logging
import boto3
import random
import json
import os
from dataclasses import dataclass
from typing import List

@dataclass
class OrderItem:
    item_id: str
    quantity: int

@dataclass
class OrderPayload:
    order_id: str
    customer_id: str
    items: List[OrderItem]

logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('events')
bus_name = os.environ.get('EVENT_BUS_NAME', 'fulfillment-dev-event-bus')
fulfillment_table = boto3.resource('dynamodb').Table(os.environ.get('FULFILLMENT_TABLE_NAME', 'fulfillment'))
service_name = 'fulfillment-service'    

# Fulfillment Service
# Publish OrderShipped and Fulfillment failed event
def handler(event, context):
    try:
        record = event.get('Records', [])
        body = json.loads(record[0]['body'])
        detail = body['detail']

        orderInfo = OrderPayload(
            order_id=detail['order_id'],
            customer_id=detail['customer_id'],
            items=[OrderItem(**item) for item in detail['items']]
        )

        fulfilled = simulate_fulfillment(orderInfo.order_id)

        fulfillment_detail = {
            'order_id': orderInfo.order_id,
            'customer_id': orderInfo.customer_id,
            'items': [{"item_id": item.item_id, "quantity": item.quantity} for item in orderInfo.items]
        }

        failure_reason = None
        if not fulfilled:
            failure_reason = get_failure_reason()
            fulfillment_detail['failure_reason'] = failure_reason

        fulfillment_record = {
            "order_id": fulfillment_detail['order_id'],
            "status": "FAILED" if failure_reason else "FULFILLED",
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        if failure_reason:
            fulfillment_record["failure_reason"] = failure_reason
            
        fulfillment_table.put_item(Item=fulfillment_record)   

        response = client.put_events(
            Entries = [
                {
                    'EventBusName': bus_name,
                    'Source': service_name,
                    'DetailType': 'OrderShipped' if fulfilled else 'FulfillmentFailed',
                    'Detail': json.dumps(fulfillment_detail)
                }
            ]
        )

        if response['FailedEntryCount'] > 0:
            logger.error("Failed to publish event: %s", response['Entries'])
            raise RuntimeError(f"Failed to publish fulfillment event for order_id={fulfillment_detail.get('order_id')}")

        logger.info("Published event detail_type=%s order_id=%s", 
                    'OrderShipped' if fulfilled else 'FulfillmentFailed', 
                    fulfillment_detail.get('order_id'))
        
        return {
            "statusCode": 200
        }

    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

def simulate_fulfillment(order_id: str) -> bool:
    success = random.randint(0, 10) < 9
    logger.info("Fulfillment result=%s orderId=%s", success, order_id)
    return success

def get_failure_reason() -> str:
    failure_reason = random.randint(0,2)
    match failure_reason:
        case 0:
            return("Item unavailable")
        case 1:
            return("Carrier pickup failed")
        case 2:
            return("Fulfillment center timeout")