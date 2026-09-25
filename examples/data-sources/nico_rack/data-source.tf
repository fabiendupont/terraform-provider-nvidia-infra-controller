data "nico_rack" "example" {
  id = "resource-uuid"
}

output "rack_name" {
  value = data.nico_rack.example.name
}
