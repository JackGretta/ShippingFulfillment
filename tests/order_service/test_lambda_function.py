import json
from unittest.mock import patch
from botocore.exceptions import ClientError

def test_place_order_happy_path(order_lambda, dynamodb_tables):
    event = {
        "body": json.dumps({
            "customer_id": "cust-123",
            "items": [{"item_id": "item-001", "quantity": 2}]
        })
    }

    response = order_lambda.handler(event, context=None)

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "processing"
    order_id = body["order_id"]

    # Assert order was placed in order table
    order_item = dynamodb_tables.get_item(
        TableName="orders",
        Key={"order_id": {"S": order_id}}
    )
    assert "Item" in order_item
    assert order_item["Item"]["customer_id"]["S"] == "cust-123"

    # Assert order hit the outbox table and was not published
    outbox_scan = dynamodb_tables.scan(TableName="outbox")
    assert len(outbox_scan["Items"]) == 1
    outbox_row = outbox_scan["Items"][0]
    assert outbox_row["detail_type"]["S"] == "OrderPlaced"
    assert outbox_row["published"]["BOOL"] is False


def test_place_order_dynamodb_failure(order_lambda, dynamodb_tables):
    event = {
        "body": json.dumps({
            "customer_id": "cust-123",
            "items": [{"item_id": "item-001", "quantity": 2}]
        })
    }

    error_response = {"Error": {"Code": "TransactionCanceledException", "Message": "mocked failure"}}

    with patch.object(
        order_lambda.dynamodb_client,
        "transact_write_items",
        side_effect=ClientError(error_response, "TransactWriteItems")
    ):
        response = order_lambda.handler(event, context=None)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert body["error"] == "Failed to place order"

    # Assert nothing was written to orders table
    order_scan = dynamodb_tables.scan(TableName="orders")
    assert len(order_scan["Items"]) == 0

    # Assert nothing written to outbox table
    outbox_scan = dynamodb_tables.scan(TableName="outbox")
    assert len(outbox_scan["Items"]) == 0

def test_place_order_missing_required_field(order_lambda, dynamodb_tables):
    event = {
        "body": json.dumps({
            "customer_id": "cust-123"
            # "items": items key is required -> KeyError
        })
    }

    response = order_lambda.handler(event, context=None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "Failed to place order"

def test_place_order_malformed_item(order_lambda, dynamodb_tables):
    event = {
        "body": json.dumps({
            "customer_id": "cust-123",
            "items": [{"item_id": "item-001"}]  # missing "quantity" property -> TypeError
        })
    }

    response = order_lambda.handler(event, context=None)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "Failed to place order"

def test_place_order_invalid_json_body(order_lambda, dynamodb_tables):
    event = {
        "body": "invalid json{{{"
    }

    response = order_lambda.handler(event, context=None)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert body["error"] == "An unexpected error occurred."