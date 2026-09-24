data "nvidia_infra_controller_ssh_key_group" "example" {
  id = "resource-uuid"
}

output "ssh_key_group_name" {
  value = data.nvidia_infra_controller_ssh_key_group.example.name
}
