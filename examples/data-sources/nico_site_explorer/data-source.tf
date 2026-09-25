data "nico_site_explorer" "example" {
  id = "resource-uuid"
}

output "site_explorer_name" {
  value = data.nico_site_explorer.example.name
}
