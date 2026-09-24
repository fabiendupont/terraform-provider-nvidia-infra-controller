data "nvidia_infra_controller_subnet" "example" {
  id = "resource-uuid"
}

output "subnet_name" {
  value = data.nvidia_infra_controller_subnet.example.name
}
