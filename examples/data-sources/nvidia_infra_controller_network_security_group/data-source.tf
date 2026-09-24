data "nvidia_infra_controller_network_security_group" "example" {
  id = "resource-uuid"
}

output "network_security_group_name" {
  value = data.nvidia_infra_controller_network_security_group.example.name
}
