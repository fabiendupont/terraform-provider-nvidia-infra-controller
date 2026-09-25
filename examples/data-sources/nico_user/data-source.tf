data "nico_user" "example" {
  id = "resource-uuid"
}

output "user_name" {
  value = data.nico_user.example.name
}
