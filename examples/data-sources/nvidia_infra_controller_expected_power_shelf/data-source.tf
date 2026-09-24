data "nvidia_infra_controller_expected_power_shelf" "example" {
  id = "resource-uuid"
}

output "expected_power_shelf_name" {
  value = data.nvidia_infra_controller_expected_power_shelf.example.name
}
