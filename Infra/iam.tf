# Create IAM role
resource "aws_iam_role" "lambda_exec" {
    name = "${var.project}-${var.env}-lambda-exec-role"

    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [{
            Action = "sts:AssumeRole"
            Effect = "Allow"
            Principal = { Service = "lambda.amazonaws.com" }
        }]
    })
}

# Policies to attach to IAM role
# Existing managed AWS policies
resource "aws_iam_role_policy_attachment" "lambda_basic" {
    role = aws_iam_role.lambda_exec.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_sqs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole"
}

# Custom policy to ad to lambda_exec role
resource "aws_iam_role_policy" "lambda_eventbridge" {
  name = "${var.project}-${var.env}-lambda-eventbridge-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:PutEvents"
      Resource = aws_cloudwatch_event_bus.main.arn
    }]
  })
}
