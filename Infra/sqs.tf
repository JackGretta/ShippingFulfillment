resource "aws_sqs_queue" "service_queue" {
    for_each = toset(var.services)
    name = "${var.project}-${var.env}-${each.value}-queue"
    message_retention_seconds = 86400 # one day  
}

# resource "aws_sqs_queue" "order_queue" {
#     name = "${var.project}-${var.env}-order-queue"
#     message_retention_seconds = 86400 # one day
# }

resource "aws_sqs_queue_policy" "allow_eventbridge" {
  for_each  = toset(["inventory", "payment", "fulfillment", "notification"])
  queue_url = aws_sqs_queue.service_queue[each.value].url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.service_queue[each.value].arn
      #Condition = ...Missing right now to simplify. EventBridge could write to any queue if someone misconfigures.
    }]
  })
}