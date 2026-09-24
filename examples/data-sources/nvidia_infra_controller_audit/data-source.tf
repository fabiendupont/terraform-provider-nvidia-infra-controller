data "nvidia_infra_controller_audit" "example" {
  id = "resource-uuid"
}

output "audit_name" {
  value = data.nvidia_infra_controller_audit.example.name
}
