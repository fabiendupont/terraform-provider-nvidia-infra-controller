data "nico_expected_machine" "example" {
  id = "resource-uuid"
}

output "expected_machine_name" {
  value = data.nico_expected_machine.example.name
}
