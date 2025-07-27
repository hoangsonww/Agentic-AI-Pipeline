variable "vpc_id"          { type = string }
variable "public_subnets"  { type = list(string) }
variable "private_subnets" { type = list(string) }
variable "aws_region"      { type = string }
variable "image_tag"       { type = string }
variable "env"             { type = string }
variable "desired_count"   { type = number }
