data "nvidia_infra_controller_expected_rack" "example" {
  id = "resource-uuid"
}

output "expected_rack_name" {
  value = data.nvidia_infra_controller_expected_rack.example.name
}
