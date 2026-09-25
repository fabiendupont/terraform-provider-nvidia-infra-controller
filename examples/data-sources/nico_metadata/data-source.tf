data "nico_metadata" "example" {
  id = "resource-uuid"
}

output "metadata_name" {
  value = data.nico_metadata.example.name
}
