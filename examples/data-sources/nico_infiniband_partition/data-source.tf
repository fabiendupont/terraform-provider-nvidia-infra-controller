data "nico_infiniband_partition" "example" {
  id = "resource-uuid"
}

output "infiniband_partition_name" {
  value = data.nico_infiniband_partition.example.name
}
