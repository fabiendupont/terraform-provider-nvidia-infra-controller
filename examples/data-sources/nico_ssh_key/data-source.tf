data "nico_ssh_key" "example" {
  id = "resource-uuid"
}

output "ssh_key_name" {
  value = data.nico_ssh_key.example.name
}
