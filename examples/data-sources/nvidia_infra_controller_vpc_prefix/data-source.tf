data "nvidia_infra_controller_vpc_prefix" "example" {
  id = "resource-uuid"
}

output "vpc_prefix_name" {
  value = data.nvidia_infra_controller_vpc_prefix.example.name
}
