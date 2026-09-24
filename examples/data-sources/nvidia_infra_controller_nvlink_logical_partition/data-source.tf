data "nvidia_infra_controller_nvlink_logical_partition" "example" {
  id = "resource-uuid"
}

output "nvlink_logical_partition_name" {
  value = data.nvidia_infra_controller_nvlink_logical_partition.example.name
}
