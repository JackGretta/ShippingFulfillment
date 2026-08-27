resource "aws_sqs_queue" "service_queue" {
    for_each = toset(var.sqs_consumer_services)
    name = "${var.project}-${var.env}-${each.value}-queue"
    message_retention_seconds = 86400 # one day
    redrive_policy = jsonencode({
      deadLetterTargetArn = aws_sqs_queue.service_dlq[each.value].arn
      maxReceiveCount     = 3 # Moves to DLQ after 3 failures
  })  
}

resource "aws_sqs_queue_policy" "allow_eventbridge" {
  for_each  = toset(var.sqs_consumer_services)
  queue_url = aws_sqs_queue.service_queue[each.value].url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.service_queue[each.value].arn
      #Condition = ...Missing right now to simplify. EventBridge could write to any queue if misconfigured.
    }]
  })
}

resource "aws_sqs_queue" "service_dlq" {
    for_each = toset(var.sqs_consumer_services)
    name = "${var.project}-${var.env}-${each.value}-dlq"
    message_retention_seconds = 1209600 # 14 days
}