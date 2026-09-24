data "nvidia_infra_controller_sku" "example" {
  id = "resource-uuid"
}

output "sku_name" {
  value = data.nvidia_infra_controller_sku.example.name
}
