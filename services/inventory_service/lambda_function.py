import logging
import boto3
import os
import json
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

###############################################################

eventbridge = boto3.client("events")
EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]

# Simulated inventory store. Can move to database later
INVENTORY = {
    "ITEM-001": 50,
    "ITEM-002": 0,   # out of stock to test failure path
    "ITEM-003": 100,
}

###############################################################

def handler(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])

        detail = body.get("detail", body)
        order_id = detail["order_id"]
        item_id = detail.get("item_id", "ITEM-001") # Testing default for now
        quantity = detail.get("quantity", 1)

        logger.info("Processing inventory reservation order_id=%s item_id=%s quantity=%d", order_id, item_id, quantity)

        reserved = reserve_inventory(item_id, quantity)

        if reserved:
            publish_event(
                "InventoryReserved",
                {
                    "order_id": order_id,
                    "item_id": item_id,
                    "quantity": quantity,
                    "reserved_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        else:
            publish_event(
                "InventoryReservationFailed",
                {
                    "order_id": order_id,
                    "item_id": item_id,
                    "quantity": quantity,
                    "reason": "insufficient_stock",
                    "failed_at": datetime.now(timezone.utc).isoformat(), 
                }
            )

    return {
        "statusCode": 200
    }


def reserve_inventory(item_id: str, quantity: int) -> bool:
    """Simulate inventory check and reservation"""

    quantity_available = INVENTORY.get(item_id)

    if quantity_available is None:
        logger.Warning("Unkown item_id=%s", item_id)
        return False
    
    if quantity_available < quantity:
        logger.info("Insufficient stock available for item_id=%s available=%d requested=%d", item_id, quantity_available, quantity)

    INVENTORY[item_id] -= quantity
    logger.info("Reserved item_id=%s quantity=%d remaining=%d", item_id, quantity_available - quantity, INVENTORY[item_id])
    return True

def publish_event(detail_type: str, detail: dict) -> None:
    eventbridge.put_events(
        Entries = [
            {
                "Source": "inventory-service",
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
                "EventBusName": EVENT_BUS_NAME
            }
        ]
    )

    logger.info("Published event detail_type=%s order_id=%s", detail_type, detail.get("order_id"))