data "nvidia_infra_controller_vpc_peering" "example" {
  id = "resource-uuid"
}

output "vpc_peering_name" {
  value = data.nvidia_infra_controller_vpc_peering.example.name
}
