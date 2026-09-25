data "nico_credential_rotation" "example" {
  id = "resource-uuid"
}

output "credential_rotation_name" {
  value = data.nico_credential_rotation.example.name
}
