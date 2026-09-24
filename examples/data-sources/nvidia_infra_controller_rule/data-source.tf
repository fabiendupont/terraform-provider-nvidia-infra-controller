data "nvidia_infra_controller_rule" "example" {
  id = "resource-uuid"
}

output "rule_name" {
  value = data.nvidia_infra_controller_rule.example.name
}
