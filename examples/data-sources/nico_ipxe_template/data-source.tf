data "nico_ipxe_template" "example" {
  id = "resource-uuid"
}

output "ipxe_template_name" {
  value = data.nico_ipxe_template.example.name
}
