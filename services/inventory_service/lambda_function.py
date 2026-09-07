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
RESERVED_STATUS = "reserved"
RESTORED_STATUS = "restored"
PAYMENT_FAILED = "PaymentFailed"
dynamodb_client = boto3.client('dynamodb')
serializer = TypeSerializer()

###############################################################

# Inventory Service - processes OrderPlaced event from Order lambda or PaymentFailed to restore inventory from payment lambda
# Emits InventoryReservationFailed for notification queue or InventoryReserved for payment queue
def handler(event, context):

    # Requires batch size of 1. Otherwise failures need to be batched.
    for record in event["Records"]:
        body = json.loads(record["body"])

        detail_type = body.get("detail-type")
        detail = body.get("detail", body)
        order_id = detail["order_id"]
        items = detail["items"]

        transact_items = []

        # track index of idempotency transaction to allow for 
        if detail_type == PAYMENT_FAILED:
            logger.info("Processing inventory restoration for order_id=%s", order_id)
            idempotency_index = 0
            transact_items.append(build_inventory_idempotency_transaction_item(order_id, RESTORED_STATUS))

            for item in items:

                item_id = item["item_id"]
                quantity = item["quantity"]
                restore_item_transaction = restore_inventory(item_id, quantity)
                transact_items.append(restore_item_transaction)
        else:
            payment_token = detail["payment_token"]
            customer_id = detail["customer_id"]
            logger.info("Processing inventory reservation order_id=%s", order_id)
        
            for item in items:

                item_id = item["item_id"]
                quantity = item["quantity"]

                reserve_transaction = reserve_inventory(item_id, quantity)
                transact_items.append(reserve_transaction)

            idempotency_index = len(transact_items)
            transact_items.append(build_inventory_idempotency_transaction_item(order_id, RESERVED_STATUS))
            transact_items.append(build_outbox_inventory_reserved_transaction_item(order_id, items, customer_id, payment_token))

        try:
            dynamodb_client.transact_write_items(TransactItems=transact_items)
            logger.info("Inventory transaction committed order_id=%s detail_type=%s item_count=%d", order_id, detail_type or "OrderPlaced", len(items))
            return { "statusCode": 200 }
        except ClientError as e:
            if e.response['Error']['Code'] != 'TransactionCanceledException':
                raise

            reasons = e.response.get('CancellationReasons', []) # array of cancellation reasons for each transaction
            idempotency_reason = reasons[idempotency_index]

            if idempotency_reason['Code'] == 'ConditionalCheckFailed':
                logger.info("Tried to process duplicate order_id=%s", order_id)
                return { "statusCode": 200 }
            else:
                # check if any item failed — insufficient stock
                item_reasons = [r for i, r in enumerate(reasons) if i != idempotency_index]
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
                    return {"statusCode": 200 }
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

def build_inventory_idempotency_transaction_item(order_id: str, status: str) -> dict:
    """Builds dynamodb transaction item for an order for the inventory_idempotency table"""
    item = {
        "Put": {
            "TableName": INVENTORY_IDEMPOTENCY_TABLE_NAME,
            "Item": {
                "order_id": serializer.serialize(order_id),
                "processed_at": serializer.serialize(datetime.now(timezone.utc).isoformat()),
                "status": serializer.serialize(status)
            }
        }
    }

    if status == RESTORED_STATUS:
        # status is a reserved keyword and needs to have '#' placeholder to escape it
        item["Put"]["ConditionExpression"] = "attribute_exists(order_id) AND #s = :expected_status"
        item["Put"]["ExpressionAttributeNames"] = {"#s": "status"}
        item["Put"]["ExpressionAttributeValues"] = {
            ":expected_status": serializer.serialize(RESERVED_STATUS)
        }
    else:
        item["Put"]["ConditionExpression"] = "attribute_not_exists(order_id)"

    return item

def build_outbox_inventory_reserved_transaction_item(order_id: str, items: dict, customer_id: str, payment_token: str) -> dict:
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

def restore_inventory(item_id: str, quantity: int) -> dict:
    """Build dynamodb transaction item for inventory restoration"""
    return {
        "Update": {
            "TableName": INVENTORY_TABLE_NAME,
            "Key": {"item_id": serializer.serialize(item_id)},
            "UpdateExpression": "SET quantity_available = quantity_available + :qty",
            "ExpressionAttributeValues": {
                ":qty": serializer.serialize(quantity)
            }
        }
    }