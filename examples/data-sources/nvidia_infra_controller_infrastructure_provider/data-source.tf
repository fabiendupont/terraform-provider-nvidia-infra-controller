data "nvidia_infra_controller_infrastructure_provider" "example" {
  id = "resource-uuid"
}

output "infrastructure_provider_name" {
  value = data.nvidia_infra_controller_infrastructure_provider.example.name
}
