# locals {
#   event_rules = {
#     order_placed       = { source = "order-service",     detail_type = "OrderPlaced",       target_queue = "inventory" }
#     inventory_reserved = { source = "inventory-service", detail_type = "InventoryReserved", target_queue = "payment" }
#     payment_confirmed  = { source = "payment-service",   detail_type = "PaymentConfirmed",  target_queue = "fulfillment" }
#   }
# }

# ToDo: clean these resources up to be more structured

resource "aws_cloudwatch_event_bus" "main" {
  name = "${var.project}-${var.env}-event-bus"
}

# EventBridge rules: Who published the event. EventBridge looks for matching source and detail type to route
resource "aws_cloudwatch_event_rule" "order_placed" {
  name = "${var.project}-${var.env}-order-placed"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = ["order-service"]
    detail-type = ["OrderPlaced"]
  })
}

resource "aws_cloudwatch_event_rule" "inventory_reserved" {
  name = "${var.project}-${var.env}-inventory-reserved"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = ["inventory-service"]
    detail-type = ["InventoryReserved"]
  })
}

resource "aws_cloudwatch_event_rule" "payment_confirmed" {
  name = "${var.project}-${var.env}-payment-confirmed"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = ["payment-service"]
    detail-type = ["PaymentConfirmed"]
  })
}

resource "aws_cloudwatch_event_rule" "payment_failed" {
  name = "${var.project}-${var.env}-payment-failed"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = ["payment-service"]
    detail-type = ["PaymentFailed"]
  })
}

resource "aws_cloudwatch_event_rule" "inventory_reservation_failed" {
  name = "${var.project}-${var.env}-inventory-reservation-failed"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = ["inventory-service"]
    detail-type = ["InventoryReservationFailed"]
  })
}

resource "aws_cloudwatch_event_rule" "order_shipped" {
  name = "${var.project}-${var.env}-order-shipped"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = ["fulfillment-service"]
    detail-type = ["OrderShipped"]
  })
}

resource "aws_cloudwatch_event_rule" "fulfillment_failed" {
  name = "${var.project}-${var.env}-fulfillment-failed"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = ["fulfillment-service"]
    detail-type = ["FulfillmentFailed"]
  })
}

# End rules


# Targets (more like destination): where does event go when matched?
resource "aws_cloudwatch_event_target" "order_placed_target" {
  rule = aws_cloudwatch_event_rule.order_placed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "inventory-queue"
  arn = aws_sqs_queue.service_queue["inventory"].arn
}

resource "aws_cloudwatch_event_target" "inventory_reserved_target" {
  rule = aws_cloudwatch_event_rule.inventory_reserved.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "payment-queue"
  arn = aws_sqs_queue.service_queue["payment"].arn
}

resource "aws_cloudwatch_event_target" "inventory_reservation_failed_target" {
  rule = aws_cloudwatch_event_rule.inventory_reservation_failed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "notification-queue"
  arn = aws_sqs_queue.service_queue["notification"].arn
}

resource "aws_cloudwatch_event_target" "payment_failed_notification_target" {
  rule = aws_cloudwatch_event_rule.payment_failed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "notification-queue"
  arn = aws_sqs_queue.service_queue["notification"].arn
}

resource "aws_cloudwatch_event_target" "payment_failed_inventory_target" {
  rule = aws_cloudwatch_event_rule.payment_failed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "inventory-queue"
  arn = aws_sqs_queue.service_queue["inventory"].arn
}

resource "aws_cloudwatch_event_target" "payment_confirmed_fulfillment_target" {
  rule = aws_cloudwatch_event_rule.payment_confirmed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "fulfillment-queue"
  arn = aws_sqs_queue.service_queue["fulfillment"].arn
}

resource "aws_cloudwatch_event_target" "payment_confirmed_notification_target" {
  rule = aws_cloudwatch_event_rule.payment_confirmed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "notification-queue"
  arn = aws_sqs_queue.service_queue["notification"].arn
}

resource "aws_cloudwatch_event_target" "order_shipped_notification_target" {
  rule = aws_cloudwatch_event_rule.order_shipped.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "notification-queue"
  arn = aws_sqs_queue.service_queue["notification"].arn
}

resource "aws_cloudwatch_event_target" "fulfillment_failed_notification_target" {
  rule = aws_cloudwatch_event_rule.fulfillment_failed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id = "notification-queue"
  arn = aws_sqs_queue.service_queue["notification"].arn
}

# End targets