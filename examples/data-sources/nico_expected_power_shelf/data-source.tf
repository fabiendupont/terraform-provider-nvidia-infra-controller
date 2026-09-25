data "nico_expected_power_shelf" "example" {
  id = "resource-uuid"
}

output "expected_power_shelf_name" {
  value = data.nico_expected_power_shelf.example.name
}
