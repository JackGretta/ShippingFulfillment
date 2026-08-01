resource "aws_apigatewayv2_api" "main" {
  name = "${var.project}-${var.env}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
    api_id = aws_apigatewayv2_api.main.id
    name = "$default" # Single stage/environment for the API gateway
    auto_deploy = true
}

resource "aws_apigatewayv2_integration" "order" {
    api_id = aws_apigatewayv2_api.main.id
    integration_type = "AWS_PROXY" # Pass full request to Lambda and return result from Lambda with no modifications
    integration_uri = aws_lambda_function.service["order"].invoke_arn
    payload_format_version = "2.0" # match formatting of Lambda payloads
}

resource "aws_apigatewayv2_route" "order" {
    api_id = aws_apigatewayv2_api.main.id
    route_key = "POST /orders" # HTTP Method + Path
    target = "integrations/${aws_apigatewayv2_integration.order.id}"  
} 

# Grant API Gateway permission to invoke the Order lambda
resource "aws_lambda_permission" "apigw" {
    statement_id = "AllowAPIGatewayInvoke"
    action = "lambda:InvokeFunction"
    function_name = aws_lambda_function.service["order"].function_name
    principal = "apigateway.amazonaws.com"
    source_arn = "${aws_apigatewayv2_api.main.execution_arn}/*/POST/orders" # * allows any environment. /Post/Orders matches route key of http method + path
}