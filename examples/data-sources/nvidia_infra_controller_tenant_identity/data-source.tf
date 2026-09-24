data "nvidia_infra_controller_tenant_identity" "example" {
  id = "resource-uuid"
}

output "tenant_identity_name" {
  value = data.nvidia_infra_controller_tenant_identity.example.name
}
