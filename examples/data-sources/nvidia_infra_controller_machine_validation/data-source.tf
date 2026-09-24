data "nvidia_infra_controller_machine_validation" "example" {
  id = "resource-uuid"
}

output "machine_validation_name" {
  value = data.nvidia_infra_controller_machine_validation.example.name
}
