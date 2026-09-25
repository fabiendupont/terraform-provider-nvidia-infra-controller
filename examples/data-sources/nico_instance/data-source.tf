data "nico_instance" "example" {
  id = "resource-uuid"
}

output "instance_name" {
  value = data.nico_instance.example.name
}
