import logging
import uuid
import boto3
import os
import json
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

###############################################################

eventbridge = boto3.client("events")
bus_name = os.environ.get('EVENT_BUS_NAME', 'fulfillment-dev-event-bus')
SERVICE_NAME = "inventory-service"
INVENTORY_TABLE_NAME = os.environ.get('INVENTORY_TABLE_NAME', 'inventory')
INVENTORY_IDEMPOTENCY_TABLE_NAME = os.environ.get('INVENTORY_IDEMPOTENCY_TABLE_NAME', 'inventory_idempotency')
OUTBOX_TABLE_NAME = os.environ.get('OUTBOX_TABLE_NAME', 'outbox')
dynamodb_client = boto3.client('dynamodb')
serializer = TypeSerializer()

###############################################################

# Inventory Service - processes OrderPlaced event from Order lambda
# Emits InventoryReservationFailed for notification queue or InventoryReserved for payment queue
def handler(event, context):

    # Requires batch size of 1. Otherwise failures need to be batched.
    for record in event["Records"]:
        body = json.loads(record["body"])

        detail = body.get("detail", body)
        order_id = detail["order_id"]
        items = detail["items"]
        payment_token = detail["payment_token"]
        customer_id = detail["customer_id"]
        logger.info("Processing inventory reservation order_id=%s", order_id)

        transact_items = []
        for item in items:

            item_id = item["item_id"]
            quantity = item["quantity"]

            reserve_transaction = reserve_inventory(item_id, quantity)
            transact_items.append(reserve_transaction)

        transact_items.append(build_inventory_idempotency_transaction(order_id))
        transact_items.append(build_outbox_inventory_reserved_transaction(order_id, items, customer_id, payment_token))

        try:
            response = dynamodb_client.transact_write_items(TransactItems=transact_items)
            return { "statusCode": 200 }
        except ClientError as e:
            if e.response['Error']['Code'] != 'TransactionCanceledException':
                raise

            reasons = e.response.get('CancellationReasons', [])
            idempotency_reason = reasons[len(items)]

            if idempotency_reason['Code'] == 'ConditionalCheckFailed':
                logger.info("Tried to process duplicate order_id=%s", order_id)
                return { "statusCode": 200 }
            else:
                # check if any item failed — insufficient stock
                item_reasons = reasons[:len(items)]
                failed_items = [item for item, reason in zip(items, item_reasons) if reason['Code'] == 'ConditionalCheckFailed']

                if failed_items:
                    publish_event(
                        "InventoryReservationFailed",
                        {
                            "order_id": order_id,
                            "items": failed_items,
                            "reason": "insufficient_stock",
                            "failed_at": datetime.now(timezone.utc).isoformat(), 
                        }
                    )
                else:
                    logger.error("Unexpected transaction cancellation, order_id=%s, reasons=%s", order_id, reasons)
                    raise                

def reserve_inventory(item_id: str, quantity: int) -> dict:
    """Build dynamodb transaction item for inventory reservation"""
    return {
        "Update": {
            "TableName": INVENTORY_TABLE_NAME,
            "Key": {"item_id": serializer.serialize(item_id)},
            "UpdateExpression": "SET quantity_available = quantity_available - :qty",
            "ConditionExpression": "quantity_available >= :qty",
            "ExpressionAttributeValues": {
                ":qty": serializer.serialize(quantity)
            }
        }
    }

def publish_event(detail_type: str, detail: dict) -> None:
    response = eventbridge.put_events(
        Entries = [
            {
                "Source": "inventory-service",
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": bus_name
            }
        ]
    )

    if response['FailedEntryCount'] > 0:
        logger.error("Failed to publish event: %s", response['Entries'])
        raise RuntimeError(f"Failed to publish event detail_type={detail_type} order_id={detail.get('order_id')}")

    logger.info("Published event detail_type=%s order_id=%s", detail_type, detail.get("order_id"))

def build_inventory_idempotency_transaction(order_id: str) -> dict:
    """Builds dynamodb transaction item for an order for the inventory_idempotency table"""
    return {
        "Put": {
            "TableName": INVENTORY_IDEMPOTENCY_TABLE_NAME,
            "Item": {
                "order_id": serializer.serialize(order_id), 
                "processed_at": serializer.serialize(datetime.now(timezone.utc).isoformat())
                },
            "ConditionExpression": "attribute_not_exists(order_id)"
        }
    }

def build_outbox_inventory_reserved_transaction(order_id: str, items: dict, customer_id: str, payment_token: str) -> dict:
    """Builds dynamodb transaction item for outbox table"""
    return {
        "Put": {
            "TableName": OUTBOX_TABLE_NAME,
            "Item": {
                "outbox_id": serializer.serialize(str(uuid.uuid4())),
                "detail_type": serializer.serialize("InventoryReserved"),
                "detail": serializer.serialize({
                    "order_id": order_id,
                    "items": items,
                    "customer_id": customer_id,
                    "payment_token": payment_token,
                    "reserved_at": datetime.now(timezone.utc).isoformat()
                }),
                "source": serializer.serialize(SERVICE_NAME),
                "created_at": serializer.serialize(datetime.now(timezone.utc).isoformat()),
                "published": serializer.serialize(False)
                }
        }
    }