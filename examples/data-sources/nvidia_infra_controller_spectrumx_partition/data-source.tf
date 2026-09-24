data "nvidia_infra_controller_spectrumx_partition" "example" {
  id = "resource-uuid"
}

output "spectrumx_partition_name" {
  value = data.nvidia_infra_controller_spectrumx_partition.example.name
}
