data "nvidia_infra_controller_uefi_credential" "example" {
  id = "resource-uuid"
}

output "uefi_credential_name" {
  value = data.nvidia_infra_controller_uefi_credential.example.name
}
