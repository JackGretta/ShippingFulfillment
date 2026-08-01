import logging
import boto3
import os
import json
from datetime import datetime, timezone
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

###############################################################

eventbridge = boto3.client("events")
bus_name = os.environ.get('EVENT_BUS_NAME', 'fulfillment-dev-event-bus')
INVENTORY_TABLE = boto3.resource('dynamodb').Table(os.environ.get('INVENTORY_TABLE_NAME', 'inventory'))

###############################################################

# Inventory Service - processes OrderPlaced event from Order lambda
# Emits InventoryReservationFailed for notification queue or InventoryReserved for payment queue
def handler(event, context):

    inventory_reserved = {}
    failed_items = {}
    all_items_reserved = True

    for record in event["Records"]:
        body = json.loads(record["body"])

        detail = body.get("detail", body)
        order_id = detail["order_id"]
        items = detail["items"]
        payment_token = detail["payment_token"]
        customer_id = detail["customer_id"]
        logger.info("Processing inventory reservation order_id=%s", order_id)

        for item in items:
            item_id = item["item_id"]
            quantity = item["quantity"]
            reserved = reserve_inventory(item_id, quantity)

            if reserved:
                inventory_reserved[item_id] = quantity
            else:
                all_items_reserved = False
                failed_items[item_id] = quantity

    if all_items_reserved and inventory_reserved:
        publish_event(
            "InventoryReserved",
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "items": items,
                "payment_token": payment_token,
                "reserved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    else:
        for item_id, quantity in inventory_reserved.items():
            replenish_inventory(item_id, quantity)

        publish_event(
            "InventoryReservationFailed",
            {
                "order_id": order_id,
                "items": [{"item_id": item_id, "quantity": quantity} for item_id, quantity in failed_items.items()],
                "reason": "insufficient_stock",
                "failed_at": datetime.now(timezone.utc).isoformat(), 
            }
        )

    return {
        "statusCode": 200
    }


def reserve_inventory(item_id: str, quantity: int) -> bool:
    """Conditionally reserve inventory in DynamoDB"""

    try:
        INVENTORY_TABLE.update_item(
            Key={"product_id": item_id},
            UpdateExpression="SET quantity_available = quantity_available - :qty",
            ConditionExpression="quantity_available >= :qty",
            ExpressionAttributeValues={":qty": quantity}
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.info("Insufficient stock for item_id=%s requested=%d", item_id, quantity)
            return False
        raise

def replenish_inventory(item_id: str, quantity: int) -> bool:
    INVENTORY_TABLE.update_item(
        Key={"product_id": item_id},
        UpdateExpression="SET quantity_available = quantity_available + :qty",            
        ExpressionAttributeValues={":qty": quantity}
    )
    logger.info("Replenished inventory item_id=%s quantity=%d", item_id, quantity)
    return True

def publish_event(detail_type: str, detail: dict) -> None:
    eventbridge.put_events(
        Entries = [
            {
                "Source": "inventory-service",
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": bus_name
            }
        ]
    )

    logger.info("Published event detail_type=%s order_id=%s", detail_type, detail.get("order_id"))