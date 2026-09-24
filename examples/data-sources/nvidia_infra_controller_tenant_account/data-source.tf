data "nvidia_infra_controller_tenant_account" "example" {
  id = "resource-uuid"
}

output "tenant_account_name" {
  value = data.nvidia_infra_controller_tenant_account.example.name
}
