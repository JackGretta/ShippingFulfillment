data "archive_file" "service_zip" {
    for_each = toset(var.services)
    type = "zip"
    source_file = "../services/${each.value}_service/lambda_function.py"
    output_path = "../services/${each.value}_service/lambda_function.zip"
}

data "archive_file" "outbox_zip" {    
    type = "zip"
    source_file = "../services/publisher_service/lambda_function.py"
    output_path = "../services/publisher_service/lambda_function.zip"
}

resource "aws_lambda_function" "service" {
    for_each = toset(var.services)
    function_name = "${var.project}-${var.env}-${each.value}-service"
    role = aws_iam_role.lambda_exec.arn #use role from iam.tf
    handler = "lambda_function.handler"
    runtime = "python3.12"
    filename = data.archive_file.service_zip[each.value].output_path
    source_code_hash = data.archive_file.service_zip[each.value].output_base64sha256

    environment {
        variables = {            
            ORDERS_TABLE_NAME = aws_dynamodb_table.dynamodb_tables["orders"].name
            INVENTORY_TABLE_NAME = aws_dynamodb_table.dynamodb_tables["inventory"].name
            INVENTORY_IDEMPOTENCY_TABLE_NAME = aws_dynamodb_table.inventory_idempotency_table.name
            PAYMENTS_TABLE_NAME = aws_dynamodb_table.dynamodb_tables["payments"].name
            FULFILLMENT_TABLE_NAME = aws_dynamodb_table.dynamodb_tables["fulfillment"].name            
            OUTBOX_TABLE_NAME = aws_dynamodb_table.dynamodb_outbox_table.name
      }
    }
}

resource "aws_lambda_function" "publisher_service" {
    function_name = "${var.project}-${var.env}-publisher-service"
    role = aws_iam_role.publisher_lambda_exec.arn #use role from iam.tf
    handler = "lambda_function.handler"
    runtime = "python3.12"
    filename = data.archive_file.outbox_zip.output_path
    source_code_hash = data.archive_file.outbox_zip.output_base64sha256

    environment {
        variables = {
            EVENT_BUS_NAME = aws_cloudwatch_event_bus.main.name
            OUTBOX_TABLE_NAME = aws_dynamodb_table.dynamodb_outbox_table.name
      }
    }
}

# resource "aws_lambda_function" "order_service" {
#     function_name = "${var.project}-${var.env}-service"
#     role = aws_iam_role.lambda_exec.arn
#     handler = "lambda_function.handler"
#     runtime = "python3.12"
#     filename = data.archive_file.order_service_zip.output_path
#     source_code_hash = data.archive_file.order_service_zip.output_base64sha256
# }