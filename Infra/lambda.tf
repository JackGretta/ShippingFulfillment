data "archive_file" "service_zip" {
    for_each = toset(var.services)
    type = "zip"
    source_file = "../services/${each.value}_service/lambda_function.py"
    output_path = "../services/${each.value}_service/lambda_function.zip"
}

resource "aws_lambda_function" "service" {
    for_each = toset(var.services)
    function_name = "${var.project}-${var.env}-${each.value}-service"
    role = aws_iam_role.lambda_exec.arn
    handler = "lambda_function.handler"
    runtime = "python3.12"
    filename = data.archive_file.service_zip[each.value].output_path
    source_code_hash = data.archive_file.service_zip[each.value].output_base64sha256
}

# Individual lambda resource and data for reference
# data "archive_file" "order_service_zip" {
#     type = "zip"
#     source_file = "../services/order_service/lambda_function.py"
#     output_path = "../services/order_service/lambda_function.zip"
# }

# resource "aws_lambda_function" "order_service" {
#     function_name = "${var.project}-${var.env}-service"
#     role = aws_iam_role.lambda_exec.arn
#     handler = "lambda_function.handler"
#     runtime = "python3.12"
#     filename = data.archive_file.order_service_zip.output_path
#     source_code_hash = data.archive_file.order_service_zip.output_base64sha256
# }