import json
import logging
import uuid
import os
import boto3
import random
from typing import List
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class OrderItem:
    item_id: str
    quantity: int

@dataclass
class Order:
    customer_id: str
    items: List[OrderItem]


logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Avoid Lambda cold start 
eventbridge_client = boto3.client('events')
orders_table = boto3.resource('dynamodb').Table(os.environ.get('ORDERS_TABLE_NAME', 'orders'))
bus_name = os.environ.get('EVENT_BUS_NAME', 'fulfillment-dev-event-bus')
detail_type = 'OrderPlaced'

# Order Service
def handler(event, context):    
    # validate payload
    try:
        body = json.loads(event['body'])
        order = Order(
            customer_id=body['customer_id'],
            items = [OrderItem(**item) for item in body['items']]
        )
        order_id = str(uuid.uuid4())

        print(f"Processing order {order_id} for customer {order.customer_id}")

        order_detail = {
            'order_id': order_id,
            'customer_id': order.customer_id,
            'items': [{'item_id': item.item_id, 'quantity': item.quantity} for item in order.items],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'payment_token': generate_mock_payment_token(), # Payment info collected by front end and securely exchanged for token
            'status': "placed"
        }

        orders_table.put_item(Item=order_detail)

        # publish event to Eventbridge
        response = eventbridge_client.put_events(
            Entries=[
                {
                    'EventBusName': bus_name,
                    'Source': 'order-service',
                    'DetailType': detail_type,                
                    'Detail': json.dumps(order_detail)
                }
            ]
        )

        if response['FailedEntryCount'] > 0:
            logger.error("Failed to publish event: %s", response['Entries'])
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to publish order event'})
            }

        logger.info("Published event detail_type=%s order_id=%s", detail_type, order_detail.get("order_id"))

    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

    return {
        'statusCode': 202,
        'body': json.dumps({'order_id': order_id, 'status': 'processing'})
    }

def generate_mock_payment_token() -> str:
    random_number = random.randint(100_000_000, 999_999_999)
    return f"mock_token_{random_number}"