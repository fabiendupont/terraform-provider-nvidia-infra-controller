data "nvidia_infra_controller_instance" "example" {
  id = "resource-uuid"
}

output "instance_name" {
  value = data.nvidia_infra_controller_instance.example.name
}
