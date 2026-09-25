data "nico_instance_type" "example" {
  id = "resource-uuid"
}

output "instance_type_name" {
  value = data.nico_instance_type.example.name
}
