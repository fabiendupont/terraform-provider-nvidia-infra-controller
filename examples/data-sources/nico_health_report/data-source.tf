data "nico_health_report" "example" {
  id = "resource-uuid"
}

output "health_report_name" {
  value = data.nico_health_report.example.name
}
