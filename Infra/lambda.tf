data "archive_file" "order_service_zip" {
    type = "zip"
    source_file = "../services/order_service/lambda_function.py"
    output_path = "../services/order_service/lambda_function.zip"
}

resource "aws_lambda_function" "order_service" {
    function_name = "fulfillment-order-service"
    role = aws_iam_role.lambda_exec.arn
    handler = "lambda_function.handler"
    runtime = "python3.12"
    filename = data.archive_file.order_service_zip.output_path
    source_code_hash = data.archive_file.order_service_zip.output_base64sha256
}