data "nvidia_infra_controller_machine" "example" {
  id = "resource-uuid"
}

output "machine_name" {
  value = data.nvidia_infra_controller_machine.example.name
}
