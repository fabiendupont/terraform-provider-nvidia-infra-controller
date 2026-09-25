data "nico_expected_rack" "example" {
  id = "resource-uuid"
}

output "expected_rack_name" {
  value = data.nico_expected_rack.example.name
}
