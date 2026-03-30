resource "aws_sqs_queue" "service_queue" {
    for_each = toset(var.services)
    name = "${var.project}-${var.env}-${each.value}-queue"
    message_retention_seconds = 86400 # one day  
}

# resource "aws_sqs_queue" "order_queue" {
#     name = "${var.project}-${var.env}-order-queue"
#     message_retention_seconds = 86400 # one day
# }