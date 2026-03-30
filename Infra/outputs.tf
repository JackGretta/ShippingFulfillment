output "order_queue_url" {
    description = "URL of the order SQS queue"
    value = aws_sqs_queue.order_queue.url
}

output "order_service_arn" {
    description = "ARN of the order service Lambda"
    value = aws_lambda_function.order_service.arn
}