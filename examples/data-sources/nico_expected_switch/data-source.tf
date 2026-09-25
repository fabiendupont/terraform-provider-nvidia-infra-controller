data "nico_expected_switch" "example" {
  id = "resource-uuid"
}

output "expected_switch_name" {
  value = data.nico_expected_switch.example.name
}
