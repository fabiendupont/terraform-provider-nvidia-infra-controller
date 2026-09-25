data "nico_vpc_prefix" "example" {
  id = "resource-uuid"
}

output "vpc_prefix_name" {
  value = data.nico_vpc_prefix.example.name
}
