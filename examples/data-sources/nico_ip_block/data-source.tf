data "nico_ip_block" "example" {
  id = "resource-uuid"
}

output "ip_block_name" {
  value = data.nico_ip_block.example.name
}
