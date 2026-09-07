import json
from unittest.mock import patch

def test_reserve_happy_path(inventory_lambda, dynamodb_tables, seed_inventory_item):
    seed_inventory_item("item-001", quantity=10)

    event = _sqs_event("OrderPlaced", {
        "order_id": "order-abc",
        "customer_id": "cust-123",
        "payment_token": "mock_token_111",
        "items": [{"item_id": "item-001", "quantity": 3}],
    })

    response = inventory_lambda.handler(event, context=None)

    assert response["statusCode"] == 200

    # inventory decremented
    item = dynamodb_tables.get_item(TableName="inventory", Key={"item_id": {"S": "item-001"}})
    assert item["Item"]["quantity_available"]["N"] == "7"

    # idempotency row recorded as reserved
    idempotency = dynamodb_tables.get_item(
        TableName="inventory_idempotency", Key={"order_id": {"S": "order-abc"}}
    )
    assert idempotency["Item"]["status"]["S"] == "reserved"

    # outbox row created for InventoryReserved
    outbox_scan = dynamodb_tables.scan(TableName="outbox")
    assert len(outbox_scan["Items"]) == 1
    assert outbox_scan["Items"][0]["detail_type"]["S"] == "InventoryReserved"

def test_duplicate_order(inventory_lambda, dynamodb_tables, seed_inventory_item, seed_inventory_idempotency_row):
    # Seed inventory and inventory_idempotency table with existing order
    order_id = "order-abc"
    idempotency_status = "reserved"
    item_id = "item-001"

    seed_inventory_item(item_id, quantity=10)
    seed_inventory_idempotency_row(order_id, idempotency_status)

    event = _sqs_event("OrderPlaced", {
        "order_id": order_id,
        "customer_id": "cust-123",
        "payment_token": "mock_token_111",
        "items": [{"item_id": item_id, "quantity": 3}],
    })

    response = inventory_lambda.handler(event, context=None)

    # Assert inventory quantity is unchanged. 
    # 200 response is same as non-duplicate order so need to check state
    assert response["statusCode"] == 200

    item = dynamodb_tables.get_item(TableName="inventory", Key={"item_id": {"S": item_id}})
    assert item["Item"]["quantity_available"]["N"] == "10"

    idempotency = dynamodb_tables.get_item(
        TableName="inventory_idempotency", Key={"order_id": {"S": order_id}})
    assert idempotency["Item"]["status"]["S"] == idempotency_status

def test_insufficient_stock(inventory_lambda, dynamodb_tables, seed_inventory_item):
    order_id = "order-abc"
    item_id = "item-001"

    seed_inventory_item(item_id, quantity=1)

    event = _sqs_event("OrderPlaced", {
        "order_id": order_id,
        "customer_id": "cust-123",
        "payment_token": "mock_token_111",
        "items": [{"item_id": item_id, "quantity": 3}],
    })

    with patch.object(inventory_lambda, "eventbridge") as mock_eventbridge:
        mock_eventbridge.put_events.return_value = {"FailedEntryCount": 0, "Entries": []}
        response = inventory_lambda.handler(event, context=None)

    assert response["statusCode"] == 200

    item = dynamodb_tables.get_item(TableName="inventory", Key={"item_id": {"S": item_id}})
    assert item["Item"]["quantity_available"]["N"] == "1"

    # Assert InventoryReservationFailed is published
    mock_eventbridge.put_events.assert_called_once()
    entry = mock_eventbridge.put_events.call_args.kwargs["Entries"][0]
    assert entry["DetailType"] == "InventoryReservationFailed"

    # Assert published event matches
    published_detail = json.loads(entry["Detail"])
    assert published_detail["order_id"] == order_id
    assert published_detail["reason"] == "insufficient_stock"

    idempotency = dynamodb_tables.get_item(
        TableName="inventory_idempotency", Key={"order_id": {"S": order_id}}
    )

    assert "Item" not in idempotency

def test_restore_inventory_on_payment_failed(inventory_lambda, dynamodb_tables, seed_inventory_item, seed_inventory_idempotency_row):    
    order_id = "order-abc"
    item_id = "item-001"

    seed_inventory_item(item_id, quantity=7)
    seed_inventory_idempotency_row(order_id, "reserved")

    event = _sqs_event("PaymentFailed", {
        "order_id": order_id,
        "customer_id": "cust-123",
        "payment_token": "mock_token_111",
        "items": [{"item_id": item_id, "quantity": 3}],
    })

    response = inventory_lambda.handler(event, context=None)
    assert response["statusCode"] == 200
    
    item = dynamodb_tables.get_item(TableName="inventory", Key={"item_id": {"S": item_id}})
    assert item["Item"]["quantity_available"]["N"] == "10"

    idempotency = dynamodb_tables.get_item(
        TableName="inventory_idempotency", Key={"order_id": {"S": order_id}})
    assert idempotency["Item"]["status"]["S"] == "restored"


def _sqs_event(detail_type: str, detail: dict) -> dict:
    """Build one SQS record shaped like what EventBridge delivers"""
    return {
        "Records": [
            {
                "body": json.dumps({
                    "detail-type": detail_type,
                    "detail": detail,
                })
            }
        ]
    }    