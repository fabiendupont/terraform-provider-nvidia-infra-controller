data "nvidia_infra_controller_ipxe_template" "example" {
  id = "resource-uuid"
}

output "ipxe_template_name" {
  value = data.nvidia_infra_controller_ipxe_template.example.name
}
