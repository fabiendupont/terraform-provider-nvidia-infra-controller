data "nico_spectrumx_partition" "example" {
  id = "resource-uuid"
}

output "spectrumx_partition_name" {
  value = data.nico_spectrumx_partition.example.name
}
