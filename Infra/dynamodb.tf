locals {
    dynamodb_tables = {
        orders = {
            partition_key = "order_id"
            type = "S"
        }
        inventory = {
            partition_key = "product_id"
            type = "S"
        }
        payments = {
            partition_key = "order_id"
            type = "S"
        }
        fulfillment = {
            partition_key = "order_id"
            type = "S"
        }
    }
}

resource "aws_dynamodb_table" "dynamodb_tables" {
    for_each = local.dynamodb_tables
    
    name = each.key
    hash_key = each.value.partition_key
    billing_mode = "PAY_PER_REQUEST"
    attribute {
        name = each.value.partition_key
        type = each.value.type
    }
}