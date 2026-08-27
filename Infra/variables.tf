variable "project" {
    description = "Project name used as namespace for resources"
    type = string
    default = "fulfillment"
}

variable "region" {
    description = "AWS Region to use"
    type = string
    default = "us-east-1"
}

variable "env" {
    description = "Deployment environment"
    type = string
    default = "dev"
}

variable "services" {
    description = "List of services to provision"
    type = list(string)
    default = ["order", "inventory", "payment", "fulfillment", "notification"]
}

variable "sqs_consumer_services" {
    description = "Services that consume from SQS (excludes order because it is trigged by API Gateway)"
    type = list(string)
    default = ["inventory", "payment", "fulfillment", "notification"]
}