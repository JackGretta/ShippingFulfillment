import logging
import boto3
import os
import json
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.types import TypeDeserializer
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

###############################################################

eventbridge = boto3.client("events")
bus_name = os.environ.get('EVENT_BUS_NAME', 'fulfillment-dev-event-bus')
OUTBOX_TABLE = boto3.resource('dynamodb').Table(os.environ.get('OUTBOX_TABLE_NAME', 'outbox'))
deserializer = TypeDeserializer()

###############################################################

def handler(event, context):    

    for record in event['Records']:
        event_name = record['eventName']

        # TTL Cleanup will trigger stream and we don't want to act on Remove events
        if event_name == "REMOVE":
            continue

        ddb_data = record['dynamodb']

        raw_new_image = ddb_data.get('NewImage', {})
        clean_new_image = {k: deserializer.deserialize(v) for k, v in raw_new_image.items()}

        # Guard against the publisher service triggering itself. Only allow publisher lambda to act on events from business services
        if clean_new_image['published']:
            continue

        detail_type = clean_new_image['detail_type']
        detail = clean_new_image['detail']
        source = clean_new_image['source']
        outbox_id = clean_new_image['outbox_id']

        publish_event(detail_type, detail, source, outbox_id)

def publish_event(detail_type: str, detail: dict, source: str, outbox_id: str) -> None:
    response = eventbridge.put_events(
        Entries = [
            {
                "Source": source,
                "DetailType": detail_type,
                "Detail": json.dumps(detail, cls=DecimalEncoder),
                "EventBusName": bus_name
            }
        ]
    )

    if response['FailedEntryCount'] > 0:
        logger.error("Failed to publish event: %s", response['Entries'])
        raise RuntimeError(f"Failed to publish event detail_type={detail_type} order_id={detail.get('order_id')}")

    logger.info("Published event detail_type=%s order_id=%s", detail_type, detail.get("order_id"))

    OUTBOX_TABLE.update_item(
        Key={'outbox_id': outbox_id},
        UpdateExpression = "Set published = :published, expires_at = :ttl_seconds",
        ExpressionAttributeValues= {
            ":published": True,
            ":ttl_seconds": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        }
    )

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)    