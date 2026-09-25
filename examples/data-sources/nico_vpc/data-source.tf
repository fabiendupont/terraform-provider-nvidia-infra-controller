data "nico_vpc" "example" {
  id = "resource-uuid"
}

output "vpc_name" {
  value = data.nico_vpc.example.name
}
