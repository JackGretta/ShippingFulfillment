import os
import sys
import importlib.util
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

@pytest.fixture
def mocked_aws():
    """Activate moto's AWS patch. While this block is open, every boto3 client is rerouted to moto's in-memory mock AWS"""
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test_key_id")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test_key")
    with mock_aws():
        yield

@pytest.fixture
def dynamodb_tables(mocked_aws):    
    """While mocked_aws is paused at yield (patch still active), create a real boto3 client
    and the tables it needs"""
    client = boto3.client("dynamodb", region_name="us-east-1")

    client.create_table(
        TableName="orders",
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    client.create_table(
        TableName="outbox",
        KeySchema=[{"AttributeName": "outbox_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "outbox_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    client.create_table(
        TableName="inventory",
        KeySchema=[{"AttributeName": "item_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "item_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    client.create_table(
        TableName="inventory_idempotency",
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    return client

@pytest.fixture
def seed_inventory_idempotency_row(dynamodb_tables):
    """Seeds an inventory idempotency row
    Simulates an order_id that's already been processed"""
    def _seed(order_id: str, status: str):
        dynamodb_tables.put_item(
            TableName="inventory_idempotency",
            Item={
                "order_id": {"S": order_id},
                "processed_at": {"S": "2026-09-01T00:00:00+00:00"},
                "status": {"S": status},
            }
        )
    return _seed

def _load_lambda_module(service_name: str):
    module_name = f"{service_name}_lambda_function"
    sys.modules.pop(module_name, None)

    file_path = REPO_ROOT / "services" / service_name / "lambda_function.py"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def order_lambda(dynamodb_tables):
    import services.order_service.lambda_function as order_module # Delay execution until pytest calls this fixture, enabling mocking
    return _load_lambda_module("order_service")

@pytest.fixture
def inventory_lambda(dynamodb_tables):
    import services.inventory_service.lambda_function as inventory_module
    return inventory_module

@pytest.fixture
def seed_inventory_item(dynamodb_tables):
    """Return function so a test can seed items as needed"""
    def _seed(item_id: str, quantity: int):
        dynamodb_tables.put_item(
            TableName="inventory",
            Item={
                "item_id": {"S": item_id},
                "quantity_available": {"N": str(quantity)},
            }
        )
    return _seed