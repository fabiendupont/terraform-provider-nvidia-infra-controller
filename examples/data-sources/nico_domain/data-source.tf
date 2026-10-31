data "nico_domain" "example" {
  id = "resource-uuid"
}

output "domain_name" {
  value = data.nico_domain.example.name
}
