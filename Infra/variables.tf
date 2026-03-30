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