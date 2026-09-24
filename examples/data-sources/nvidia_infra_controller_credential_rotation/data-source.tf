data "nvidia_infra_controller_credential_rotation" "example" {
  id = "resource-uuid"
}

output "credential_rotation_name" {
  value = data.nvidia_infra_controller_credential_rotation.example.name
}
