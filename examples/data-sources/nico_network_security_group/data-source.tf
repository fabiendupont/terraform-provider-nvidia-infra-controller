data "nico_network_security_group" "example" {
  id = "resource-uuid"
}

output "network_security_group_name" {
  value = data.nico_network_security_group.example.name
}
