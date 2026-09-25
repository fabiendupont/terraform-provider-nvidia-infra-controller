data "nico_tenant_identity" "example" {
  id = "resource-uuid"
}

output "tenant_identity_name" {
  value = data.nico_tenant_identity.example.name
}
