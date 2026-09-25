data "nico_ssh_key_group" "example" {
  id = "resource-uuid"
}

output "ssh_key_group_name" {
  value = data.nico_ssh_key_group.example.name
}
