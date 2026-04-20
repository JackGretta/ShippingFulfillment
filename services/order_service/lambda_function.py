import json
import uuid
import boto3
import os
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


# Avoid Lambda cold start 
client = boto3.client('events')
bus_name = os.environ.get('EVENT_BUS_NAME', 'fulfillment-dev-event-bus')

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
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # publish event to Eventbridge
        response = client.put_events(
            Entries=[
                {
                    'EventBusName': bus_name,
                    'Source': 'order-service',
                    'DetailType': 'OrderPlaced',                
                    'Detail': json.dumps(order_detail)
                }
            ]
        )

        if response['FailedEntryCount'] > 0:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to publish order event'})
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

    return {
        'statusCode': 202,
        'body': json.dumps({'order_id': order_id, 'status': 'processing'})
    }