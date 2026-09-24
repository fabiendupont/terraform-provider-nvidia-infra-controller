data "nvidia_infra_controller_expected_switch" "example" {
  id = "resource-uuid"
}

output "expected_switch_name" {
  value = data.nvidia_infra_controller_expected_switch.example.name
}
