import json
import random
import logging
from typing import List
import boto3
import os
from dataclasses import dataclass

@dataclass
class OrderItem:
    item_id: str
    quantity: int

@dataclass
class OrderPayload:
    order_id: str
    customer_id: str
    items: List[OrderItem]
    payment_token: str

logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('events')
bus_name = os.environ.get('EVENT_BUS_NAME', 'fulfillment-dev-event-bus')
service_name = 'payment-service'

# Payment Service
# Emits PaymentConfirmed or PaymentFailed event for Fulfillment
def handler(event, context):
    try:            
        record = event.get('Records', [])
        body = json.loads(record[0]['body'])
        detail = body['detail']

        order = OrderPayload(
            order_id=detail['order_id'],
            customer_id=detail['customer_id'],
            payment_token=detail['payment_token'],
            items=[OrderItem(**item) for item in detail["items"]]
        )

        payment_status = simulate_payment(order.order_id, order.payment_token)    

        order_detail = {
            'order_id': order.order_id,
            'customer_id': order.customer_id,
            'items': [{'item_id': item.item_id, 'quantity': item.quantity} for item in order.items],
            'payment_token': order.payment_token
        }

        if not payment_status:
            failure_reason = get_failure_reason()
            order_detail['failure_reason'] = failure_reason

        response = client.put_events(
            Entries = [
                {
                    'EventBusName': bus_name,
                    'Source': service_name,
                    'DetailType': 'PaymentConfirmed' if payment_status else 'PaymentFailed',                
                    'Detail': json.dumps(order_detail)
                }
            ]
        )

        if response['FailedEntryCount'] > 0:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to publish payment event'})
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
    
def simulate_payment(order_id: str, payment_token: str) -> bool:
    success = random.randint(0, 10) >= 9
    logger.info("Payment result=%s orderId=%s", success, order_id)
    return success

def get_failure_reason() -> str:
    failure_reason = random.randint(0,2)
    match failure_reason:
        case 0:
            return("Card decline")
        case 1:
            return("Insufficient funds")
        case 2:
            return("Vendor error")