data "nico_operating_system" "example" {
  id = "resource-uuid"
}

output "operating_system_name" {
  value = data.nico_operating_system.example.name
}
