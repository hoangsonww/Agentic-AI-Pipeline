variable "aws_region"     { type = string }
variable "aws_profile"    { type = string  default = "default" }
variable "env"            { type = string  default = "dev" }
variable "image_tag"      { type = string  default = "latest" }
variable "desired_count"  { type = number  default = 1 }
variable "vpc_id"         { type = string }
variable "public_subnets" { type = list(string) }
