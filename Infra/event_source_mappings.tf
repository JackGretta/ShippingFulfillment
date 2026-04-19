# When message lands in queue, invoke lambdas

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
    for_each = toset(["inventory", "payment", "fulfillment", "notification"])
    event_source_arn = aws_sqs_queue.service_queue[each.value].arn
    function_name = aws_lambda_function.service[each.value].arn
    batch_size = 1
}