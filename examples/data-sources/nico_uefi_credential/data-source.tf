data "nico_uefi_credential" "example" {
  id = "resource-uuid"
}

output "uefi_credential_name" {
  value = data.nico_uefi_credential.example.name
}
