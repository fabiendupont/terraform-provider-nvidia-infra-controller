data "nico_expected_rack_group" "example" {
  id = "resource-uuid"
}

output "expected_rack_group_name" {
  value = data.nico_expected_rack_group.example.name
}
