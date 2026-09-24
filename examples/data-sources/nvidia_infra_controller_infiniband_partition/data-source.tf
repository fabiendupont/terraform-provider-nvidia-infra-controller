data "nvidia_infra_controller_infiniband_partition" "example" {
  id = "resource-uuid"
}

output "infiniband_partition_name" {
  value = data.nvidia_infra_controller_infiniband_partition.example.name
}
