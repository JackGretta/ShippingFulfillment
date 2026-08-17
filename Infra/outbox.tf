resource "aws_dynamodb_table" "dynamodb_outbox_table" {
    name = "outbox"
    hash_key = "outbox_id"
    billing_mode = "PAY_PER_REQUEST"
    stream_enabled = true
    stream_view_type = "NEW_IMAGE"
    attribute {
        name = "outbox_id"
        type = "S"
    }

    ttl {
        attribute_name = "expires_at"
        enabled        = true
    }
}