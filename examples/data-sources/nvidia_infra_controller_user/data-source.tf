data "nvidia_infra_controller_user" "example" {
  id = "resource-uuid"
}

output "user_name" {
  value = data.nvidia_infra_controller_user.example.name
}
