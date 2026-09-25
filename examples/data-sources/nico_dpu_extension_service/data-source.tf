data "nico_dpu_extension_service" "example" {
  id = "resource-uuid"
}

output "dpu_extension_service_name" {
  value = data.nico_dpu_extension_service.example.name
}
