resource "aws_dynamodb_table" "inventory_idempotency_table" {
    name = "inventory_idempotency"
    hash_key = "order_id"
    billing_mode = "PAY_PER_REQUEST"
    attribute {
        name = "order_id"
        type = "S"
    }
}