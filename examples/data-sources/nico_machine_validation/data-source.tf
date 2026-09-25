data "nico_machine_validation" "example" {
  id = "resource-uuid"
}

output "machine_validation_name" {
  value = data.nico_machine_validation.example.name
}
