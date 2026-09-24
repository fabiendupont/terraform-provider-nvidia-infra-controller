data "nvidia_infra_controller_expected_machine" "example" {
  id = "resource-uuid"
}

output "expected_machine_name" {
  value = data.nvidia_infra_controller_expected_machine.example.name
}
