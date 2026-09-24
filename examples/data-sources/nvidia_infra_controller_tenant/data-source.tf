data "nvidia_infra_controller_tenant" "example" {
  id = "resource-uuid"
}

output "tenant_name" {
  value = data.nvidia_infra_controller_tenant.example.name
}
