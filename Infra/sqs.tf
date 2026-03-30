resource "aws_sqs_queue" "order_queue" {
    name = "fulfillment-order-queue"
    message_retention_seconds = 86400 # one day
}