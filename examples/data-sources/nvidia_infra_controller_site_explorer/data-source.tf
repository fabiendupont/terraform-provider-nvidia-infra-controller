data "nvidia_infra_controller_site_explorer" "example" {
  id = "resource-uuid"
}

output "site_explorer_name" {
  value = data.nvidia_infra_controller_site_explorer.example.name
}
