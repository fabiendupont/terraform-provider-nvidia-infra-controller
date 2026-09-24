data "nvidia_infra_controller_site" "example" {
  id = "resource-uuid"
}

output "site_name" {
  value = data.nvidia_infra_controller_site.example.name
}
