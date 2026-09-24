data "nvidia_infra_controller_ssh_key" "example" {
  id = "resource-uuid"
}

output "ssh_key_name" {
  value = data.nvidia_infra_controller_ssh_key.example.name
}
