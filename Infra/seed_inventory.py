import boto3
import os

inventory_table = boto3.resource('dynamodb').Table(os.environ.get('INVENTORY_TABLE_NAME', 'inventory'))

inventory = [
    {
        "item_id": "ITEM-0001",
        "item_name": "paper towel",
        "quantity_available": 10
    },
    {
        "item_id": "ITEM-2912",
        "item_name": "power bank",
        "quantity_available": 1
    },
    {
        "item_id": "ITEM-9317",
        "item_name": "basketball",
        "quantity_available": 5
    }
]

with inventory_table.batch_writer() as batch:
    for item in inventory:
        batch.put_item(Item=item)