import json
import logging
import uuid
import os
import boto3
import random
from typing import List
from dataclasses import dataclass
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer

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
ORDERS_TABLE_NAME = os.environ.get('ORDERS_TABLE_NAME', 'orders')
OUTBOX_TABLE_NAME = os.environ.get('OUTBOX_TABLE_NAME', 'outbox')
DETAIL_TYPE = 'OrderPlaced'
SERVICE_NAME = "order-service"
dynamodb_client = boto3.client('dynamodb')

serializer = TypeSerializer()

def handler(event, context):    
    # validate payload
    try:
        body = json.loads(event['body'])
        order = Order(
            customer_id=body['customer_id'],
            items = [OrderItem(**item) for item in body['items']]
        )

        order_id = str(uuid.uuid4())
        logger.info("Processing order order_id=%s customer_id=%s", order_id, order.customer_id)

        order_detail = {
            'order_id': order_id,
            'customer_id': order.customer_id,
            'items': [{'item_id': item.item_id, 'quantity': item.quantity} for item in order.items],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'payment_token': generate_mock_payment_token(), # Payment info collected by front end and securely exchanged for token
            'status': "placed"
        }

        
        transactions = [
                            build_order_transaction(order_detail), 
                            build_outbox_order_placed_transaction(order_detail)
                        ]

        try:
            dynamodb_client.transact_write_items(TransactItems=transactions)
            
            return {
                        "statusCode": 202,
                        "body": json.dumps({'order_id': order_id, 'status': 'processing'}) 
                    }
        except ClientError as e:
            logger.error("Unexpected transaction cancellation, order_id=%s, error=%s", order_id, e)

            return {
                "statusCode": 500,
                "body": json.dumps({'error': 'Failed to place order'})
            }
    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({'error': 'Failed to place order'})
        }                
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({'error': 'An unexpected error occurred.'})
        } 

def build_order_transaction(order_detail: dict) -> dict:
        return {
            "Put": {
                "TableName": ORDERS_TABLE_NAME,
                "Item": {
                    "order_id": serializer.serialize(order_detail['order_id']),
                    "customer_id": serializer.serialize(order_detail['customer_id']),
                    "items": serializer.serialize(order_detail['items']),
                    "timestamp": serializer.serialize(order_detail['timestamp']),
                    "payment_token": serializer.serialize(order_detail['payment_token']),
                    "status": serializer.serialize(order_detail['status'])
                }                
            }
        }

def build_outbox_order_placed_transaction(order_detail: dict) -> dict:
    return {
        "Put": {
            "TableName": OUTBOX_TABLE_NAME,
            "Item": {
                "outbox_id": serializer.serialize(str(uuid.uuid4())),
                "detail_type": serializer.serialize(DETAIL_TYPE),
                "detail": serializer.serialize({
                    "order_id": order_detail['order_id'],
                    "customer_id": order_detail['customer_id'],
                    "items": order_detail['items'],
                    "timestamp": order_detail['timestamp'],
                    "payment_token": order_detail['payment_token'],
                    "status": order_detail['status']
                }),
                "source": serializer.serialize(SERVICE_NAME),
                "created_at": serializer.serialize(datetime.now(timezone.utc).isoformat()),
                "published": serializer.serialize(False)
            }
        }
    }

def generate_mock_payment_token() -> str:
    random_number = random.randint(100_000_000, 999_999_999)
    return f"mock_token_{random_number}"