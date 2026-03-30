output "queue_urls" {
    description = "URLs of all service SQS queues"
    value = { for k, v in aws_sqs_queue.service_queue : k => v.url }
}

output "lambda_arns" {
    description = "ARNs of all service Lambda functions"
    value = { for k, v in aws_lambda_function.service : k => v.arn }
}

# output "order_queue_url" {
#     description = "URL of the order SQS queue"
#     value = aws_sqs_queue.order_queue.url
# }

# output "order_service_arn" {
#     description = "ARN of the order service Lambda"
#     value = aws_lambda_function.order_service.arn
# }