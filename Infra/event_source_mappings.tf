# When message lands in queue, invoke lambdas

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
    for_each = toset(["inventory", "payment", "fulfillment", "notification"])
    event_source_arn = aws_sqs_queue.service_queue[each.value].arn
    function_name = aws_lambda_function.service[each.value].arn
    batch_size = 1
}

resource "aws_lambda_event_source_mapping" "dynamodb_stream_trigger" {    
    event_source_arn = aws_dynamodb_table.dynamodb_outbox_table.stream_arn
    function_name = aws_lambda_function.publisher_service.arn
    starting_position = "LATEST"
    batch_size = 1
}