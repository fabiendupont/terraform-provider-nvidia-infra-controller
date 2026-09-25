data "nico_machine" "example" {
  id = "resource-uuid"
}

output "machine_name" {
  value = data.nico_machine.example.name
}
