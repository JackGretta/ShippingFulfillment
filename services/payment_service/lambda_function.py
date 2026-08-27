from datetime import datetime, timezone
import json
import random
import logging
from typing import List
import uuid
import boto3
import os
from dataclasses import dataclass
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

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

PAYMENTS_TABLE_NAME = os.environ.get('PAYMENTS_TABLE_NAME', 'payments')
OUTBOX_TABLE_NAME = os.environ.get('OUTBOX_TABLE_NAME', 'outbox')
PAYMENT_CONFIRMED = "PaymentConfirmed"
PAYMENT_FAILED = "PaymentFailed"
SERVICE_NAME = 'payment-service'

dynamodb_client = boto3.client('dynamodb')
serializer = TypeSerializer();

# Emits PaymentConfirmed event for Fulfillment or PaymentFailed for Notification
def handler(event, context):
    try:            
        records = event.get('Records', [])
        if not records:
            logger.error("No records found in event")
            raise ValueError("Event contained no records")
        
        body = json.loads(records[0]['body'])
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

        failure_reason = None
        if not payment_status:
            failure_reason = get_failure_reason()
            order_detail['failure_reason'] = failure_reason

        payment_record = {
            'order_id': order_detail['order_id'],
            'payment_token': order_detail['payment_token'],
            'status': 'FAILED' if failure_reason else 'CONFIRMED',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        if failure_reason:
            payment_record["failure_reason"] = failure_reason

        transact_items = []
        transact_items.append(build_payment_transaction_item(payment_record))
        transact_items.append(build_outbox_transaction_item(order_detail))

        try:
            dynamodb_client.transact_write_items(TransactItems=transact_items)
            return {"statusCode": 200}
        except ClientError as e:
            if e.response['Error']['Code'] != 'TransactionCanceledException':
                raise

            reasons = e.response.get('CancellationReasons', [])
            payment_reason = reasons[0] # Failure should only happen if trying to deliver existing payment_record

            if payment_reason['Code'] == 'ConditionalCheckFailed':
                logger.info("Duplicate payment delivery detected, order_id=%s", order.order_id)
                return {"statusCode": 200}
            else:
                logger.error("Unexpected transaction failure, order_id=%s, error=%s", order.order_id, e)
                raise
    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    
def simulate_payment(order_id: str, payment_token: str) -> bool:
    success = random.randint(0, 10) < 9
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

def build_payment_transaction_item(payment_record: dict) -> dict:
    """Builds dynamodb transaction item for the payments table"""
    return {
        "Put": {
            "TableName": PAYMENTS_TABLE_NAME,
            "Item": serialize_item(payment_record),
            "ConditionExpression": "attribute_not_exists(order_id)"
        }
    }

def build_outbox_transaction_item(order_detail) -> dict:
    """Builds dynamodb transaction item for the outbox table"""
    detail_type = PAYMENT_FAILED if order_detail.get("failure_reason", "") else PAYMENT_CONFIRMED
    return {
        "Put": {
            "TableName": OUTBOX_TABLE_NAME,
            "Item": {
                "outbox_id": serializer.serialize(str(uuid.uuid4())),
                "detail_type": serializer.serialize(detail_type),
                "detail": serializer.serialize(order_detail),
                "source": serializer.serialize(SERVICE_NAME),
                "created_at": serializer.serialize(datetime.now(timezone.utc).isoformat()),
                "published": serializer.serialize(False)
            }
        }
    }

def serialize_item(item: dict) -> dict:
    return {k: serializer.serialize(v) for k, v in item.items()}