data "nvidia_infra_controller_allocation" "example" {
  id = "resource-uuid"
}

output "allocation_name" {
  value = data.nvidia_infra_controller_allocation.example.name
}
