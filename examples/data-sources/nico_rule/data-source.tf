data "nico_rule" "example" {
  id = "resource-uuid"
}

output "rule_name" {
  value = data.nico_rule.example.name
}
