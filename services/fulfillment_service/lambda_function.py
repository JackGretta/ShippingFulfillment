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

        if not fulfilled:
            failure_reason = get_failure_reason()
            fulfillment_detail['failure_reason'] = failure_reason

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
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to publish fulfillment event'})
            }
        
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