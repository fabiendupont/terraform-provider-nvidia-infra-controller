data "nvidia_infra_controller_metadata" "example" {
  id = "resource-uuid"
}

output "metadata_name" {
  value = data.nvidia_infra_controller_metadata.example.name
}
