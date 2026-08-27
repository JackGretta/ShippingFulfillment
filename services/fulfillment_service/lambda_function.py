from datetime import datetime, timezone
import logging
import uuid
import boto3
import random
import json
import os
from dataclasses import dataclass
from typing import List
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

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FULFILLMENT_TABLE_NAME = os.environ.get('FULFILLMENT_TABLE_NAME', 'fulfillment')
OUTBOX_TABLE_NAME = os.environ.get('OUTBOX_TABLE_NAME', 'outbox')
ORDER_SHIPPED = "OrderShipped"
FULFILLMENT_FAILED = "FulfillmentFailed"
SERVICE_NAME = 'fulfillment-service'

serializer = TypeSerializer()
dynamodb_client = boto3.client('dynamodb')

# Fulfillment Service
# Publish OrderShipped and Fulfillment failed event
def handler(event, context):
    try:
        records = event.get('Records', [])
        if not records:
            logger.error("No records found in event")
            raise ValueError("Event contained no records")

        body = json.loads(records[0]['body'])
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

        transaction_items = []
        transaction_items.append(build_fulfillment_transaction_item(fulfillment_record))
        transaction_items.append(build_outbox_transaction_item(fulfillment_detail))

        try:
            dynamodb_client.transact_write_items(TransactItems=transaction_items)
            return { "statusCode": 200 }
        except ClientError as e:
            if e.response['Error']['Code'] != 'TransactionCanceledException':
                raise

            reasons = e.response.get('CancellationReasons', [])
            fulfillment_condition_reason = reasons[0] # Failure should only happen if trying to deliver existing fulfillment record

            if fulfillment_condition_reason['Code'] == 'ConditionalCheckFailed':
                logger.info("Duplicate fulfillment delivery detected, order_id=%s", orderInfo.order_id)
                return {"statusCode": 200}
            else:
                logger.error("Unexpected transaction failure, order_id=%s, error=%s", orderInfo.order_id, e)
                raise                    
    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

def build_fulfillment_transaction_item(fulfillment_record):
    """Builds dynamodb transaction item for the fulfillment table"""
    return {
        "Put": {
            "TableName": FULFILLMENT_TABLE_NAME,
            "Item": serialize_item(fulfillment_record),
            "ConditionExpression": "attribute_not_exists(order_id)"
        }
    }
def build_outbox_transaction_item(fulfillment_detail):
    """Builds the dynamodb transaction item for the outbox table"""
    detail_type = FULFILLMENT_FAILED if fulfillment_detail.get("failure_reason", "") else ORDER_SHIPPED
    return {
        "Put": {
            "TableName": OUTBOX_TABLE_NAME,
            "Item": {
                "outbox_id": serializer.serialize(str(uuid.uuid4())),
                "detail_type": serializer.serialize(detail_type),
                "detail": serializer.serialize(fulfillment_detail),
                "source": serializer.serialize(SERVICE_NAME),
                "created_at": serializer.serialize(datetime.now(timezone.utc).isoformat()),
                "published": serializer.serialize(False)
            }
        }
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

def serialize_item(item: dict) -> dict:
    return {k: serializer.serialize(v) for k, v in item.items()}