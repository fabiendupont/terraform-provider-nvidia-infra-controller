data "nvidia_infra_controller_instance_type" "example" {
  id = "resource-uuid"
}

output "instance_type_name" {
  value = data.nvidia_infra_controller_instance_type.example.name
}
