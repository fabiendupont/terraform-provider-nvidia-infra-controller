data "nico_audit" "example" {
  id = "resource-uuid"
}

output "audit_name" {
  value = data.nico_audit.example.name
}
