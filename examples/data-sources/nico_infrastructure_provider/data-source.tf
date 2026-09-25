data "nico_infrastructure_provider" "example" {
  id = "resource-uuid"
}

output "infrastructure_provider_name" {
  value = data.nico_infrastructure_provider.example.name
}
