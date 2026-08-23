# Create IAM role. Define who can use the identity
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

resource "aws_iam_role" "publisher_lambda_exec" {
    name = "${var.project}-${var.env}-publisher-lambda-exec-role"

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

resource "aws_iam_role_policy_attachment" "dynamodb_streams" {  
  role       = aws_iam_role.publisher_lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaDynamoDBExecutionRole"
}

resource "aws_iam_role_policy_attachment" "publisher_basic" {
    role = aws_iam_role.publisher_lambda_exec.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}


# Custom policy to ad to lambda_exec role
resource "aws_iam_role_policy" "publisher_eventbridge" {
  name = "${var.project}-${var.env}-publisher-eventbridge-policy"
  role = aws_iam_role.publisher_lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:PutEvents"
      Resource = aws_cloudwatch_event_bus.main.arn
    }]
  })
}

resource "aws_iam_role_policy" "dynamodb_access" {
  name = "${var.project}-${var.env}-dynamodb-access-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
      Resource = values(aws_dynamodb_table.dynamodb_tables)[*].arn # values pulls to list and [*] iterates 
    }]
  })
}

resource "aws_iam_role_policy" "dynamodb_outbox_access" {
  name = "${var.project}-${var.env}-dynamodb-outbox-access-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["dynamodb:PutItem"]
      Resource = aws_dynamodb_table.dynamodb_outbox_table.arn
    }]
  })
}

resource "aws_iam_role_policy" "publisher_outbox_update" {
  name = "${var.project}-${var.env}-outbox-update-policy"
  role = aws_iam_role.publisher_lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["dynamodb:UpdateItem"]
      Resource = aws_dynamodb_table.dynamodb_outbox_table.arn
    }]
  })
}


resource "aws_iam_role_policy" "inventory_idempotency_check" {
  name = "${var.project}-${var.env}-inventory_idempotency-check-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["dynamodb:PutItem"]
      Resource = aws_dynamodb_table.inventory_idempotency_table.arn
    }]
  })
}
