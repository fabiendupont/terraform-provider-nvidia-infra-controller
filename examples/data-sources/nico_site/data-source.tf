data "nico_site" "example" {
  id = "resource-uuid"
}

output "site_name" {
  value = data.nico_site.example.name
}
