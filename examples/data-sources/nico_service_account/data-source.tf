data "nico_service_account" "example" {
  id = "resource-uuid"
}

output "service_account_name" {
  value = data.nico_service_account.example.name
}
