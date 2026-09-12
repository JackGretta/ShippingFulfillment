import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from boto3.dynamodb.types import TypeSerializer

_serializer = TypeSerializer()

def test_publisher_happy_path(publisher_lambda, dynamodb_tables):
    outbox_id = "outbox-abc"
    item = {
        "outbox_id": outbox_id,
        "detail_type": "OrderPlaced",
        "detail": {
            "order_id": "order-abc",
            "customer_id": "cust-123",
            "items": [{"item_id": "item-001", "quantity": 3}],
        },
        "source": "order-service",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "published": False,
    }

    # Seed the outbox row the same as the Lambda
    seralized_item = {k : _serializer.serialize(v) for k, v in item.items()}
    dynamodb_tables.put_item(TableName="outbox", Item=seralized_item)

    event = _stream_event("INSERT", item)

    with patch.object(publisher_lambda, "eventbridge") as mock_eventbridge:
        mock_eventbridge.put_events.return_value = {"FailedEntryCount": 0, "Entries": []}
        publisher_lambda.handler(event, context=None)

    # ASSERT
    mock_eventbridge.put_events.assert_called_once()
    entry = mock_eventbridge.put_events.call_args.kwargs["Entries"][0]
    assert entry["Source"] == "order-service"
    assert entry["DetailType"] == "OrderPlaced"

    # Assert decimalEncoder 
    published_detail = json.loads(entry["Detail"])
    assert published_detail["items"][0]["quantity"] == 3

    # Row gets set to published and TTL is set
    row = dynamodb_tables.get_item(TableName="outbox", Key={"outbox_id": {"S": outbox_id}})
    assert row["Item"]["published"]["BOOL"] is True
    assert "expires_at" in row["Item"]

def test_publisher_skips_remove_events(publisher_lambda, dynamodb_tables):
    # Remove events are skipped
    event = {"Records": [{"eventName": "REMOVE"}]}

    with patch.object(publisher_lambda, "eventbridge") as mock_eventbridge:
        publisher_lambda.handler(event, context=None)

    mock_eventbridge.put_events.assert_not_called()    

def test_publisher_skips_already_published(publisher_lambda, dynamodb_tables):
    item = {
        "outbox_id": "outbox-def",
        "detail_type": "OrderPlaced",
        "detail": {"order_id": "order-def"},
        "source": "order-service",
        "published": True,  # Protects self-trigger
    }
    event = _stream_event("MODIFY", item)

    with patch.object(publisher_lambda, "eventbridge") as mock_eventbridge:
        publisher_lambda.handler(event, context=None)

    mock_eventbridge.put_events.assert_not_called()

def test_publisher_raises_on_publish_failure(publisher_lambda, dynamodb_tables):
    outbox_id = "outbox-ghi"
    item = {
        "outbox_id": outbox_id,
        "detail_type": "OrderPlaced",
        "detail": {"order_id": "order-ghi"},
        "source": "order-service",
        "published": False,
    }
    serialized_item = {k: _serializer.serialize(v) for k, v in item.items()}
    dynamodb_tables.put_item(TableName="outbox", Item=serialized_item)

    event = _stream_event("INSERT", item)

    # Simulate publish failure
    with patch.object(publisher_lambda, "eventbridge") as mock_eventbridge:
        mock_eventbridge.put_events.return_value = {
            "FailedEntryCount": 1,
            "Entries": [{"ErrorCode": "InternalFailure"}],
        }
        with pytest.raises(RuntimeError):
            publisher_lambda.handler(event, context=None)

    # Assert row stays unpublished to allow reprocessing 
    row = dynamodb_tables.get_item(TableName="outbox", Key={"outbox_id": {"S": outbox_id}})
    assert row["Item"]["published"]["BOOL"] is False    

def _stream_event(event_name: str, new_image: dict) -> dict:
    record = { "eventName": event_name }
    if new_image is not None:
        record["dynamodb"] = {
            "NewImage": {k: _serializer.serialize(v) for k, v in new_image.items()}            
        }
    return { "Records": [record] }