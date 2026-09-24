data "nvidia_infra_controller_tray" "example" {
  id = "resource-uuid"
}

output "tray_name" {
  value = data.nvidia_infra_controller_tray.example.name
}
