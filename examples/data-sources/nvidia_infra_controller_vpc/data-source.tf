data "nvidia_infra_controller_vpc" "example" {
  id = "resource-uuid"
}

output "vpc_name" {
  value = data.nvidia_infra_controller_vpc.example.name
}
