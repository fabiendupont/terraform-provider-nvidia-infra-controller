data "nvidia_infra_controller_rack" "example" {
  id = "resource-uuid"
}

output "rack_name" {
  value = data.nvidia_infra_controller_rack.example.name
}
