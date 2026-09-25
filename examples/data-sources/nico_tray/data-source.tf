data "nico_tray" "example" {
  id = "resource-uuid"
}

output "tray_name" {
  value = data.nico_tray.example.name
}
