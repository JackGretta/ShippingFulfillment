locals {
  allowed_queue_rules = {
    inventory = [
      aws_cloudwatch_event_rule.order_placed.arn,
      aws_cloudwatch_event_rule.payment_failed.arn,
    ]
    payment = [
      aws_cloudwatch_event_rule.inventory_reserved.arn,
    ]
    fulfillment = [
      aws_cloudwatch_event_rule.payment_confirmed.arn,
    ]
    notification = [
      aws_cloudwatch_event_rule.inventory_reservation_failed.arn,
      aws_cloudwatch_event_rule.payment_failed.arn,
      aws_cloudwatch_event_rule.payment_confirmed.arn,
      aws_cloudwatch_event_rule.order_shipped.arn,
      aws_cloudwatch_event_rule.fulfillment_failed.arn,
    ]
  }
}

resource "aws_sqs_queue" "service_queue" {
    for_each = toset(var.sqs_consumer_services)
    name = "${var.project}-${var.env}-${each.value}-queue"
    message_retention_seconds = 86400 # one day
    redrive_policy = jsonencode({
      deadLetterTargetArn = aws_sqs_queue.service_dlq[each.value].arn
      maxReceiveCount = 3 # Moves to DLQ after 3 failures
  })  
}

resource "aws_sqs_queue_policy" "allow_eventbridge" {
  for_each  = toset(var.sqs_consumer_services)
  queue_url = aws_sqs_queue.service_queue[each.value].url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action = "sqs:SendMessage"
      Resource = aws_sqs_queue.service_queue[each.value].arn
      Condition = { ArnEquals = { "aws:SourceArn" = local.allowed_queue_rules[each.value] } }
    }]
  })
}

resource "aws_sqs_queue" "service_dlq" {
    for_each = toset(var.sqs_consumer_services)
    name = "${var.project}-${var.env}-${each.value}-dlq"
    message_retention_seconds = 1209600 # 14 days
}