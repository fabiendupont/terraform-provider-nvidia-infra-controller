data "nico_subnet" "example" {
  id = "resource-uuid"
}

output "subnet_name" {
  value = data.nico_subnet.example.name
}
