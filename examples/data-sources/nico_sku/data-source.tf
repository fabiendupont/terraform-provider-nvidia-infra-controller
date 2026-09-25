data "nico_sku" "example" {
  id = "resource-uuid"
}

output "sku_name" {
  value = data.nico_sku.example.name
}
