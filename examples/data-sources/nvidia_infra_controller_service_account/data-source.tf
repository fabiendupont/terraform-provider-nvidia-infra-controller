data "nvidia_infra_controller_service_account" "example" {
  id = "resource-uuid"
}

output "service_account_name" {
  value = data.nvidia_infra_controller_service_account.example.name
}
