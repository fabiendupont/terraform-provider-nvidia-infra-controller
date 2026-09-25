data "nico_tenant" "example" {
  id = "resource-uuid"
}

output "tenant_name" {
  value = data.nico_tenant.example.name
}
