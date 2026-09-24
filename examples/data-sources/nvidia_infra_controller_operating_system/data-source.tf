data "nvidia_infra_controller_operating_system" "example" {
  id = "resource-uuid"
}

output "operating_system_name" {
  value = data.nvidia_infra_controller_operating_system.example.name
}
