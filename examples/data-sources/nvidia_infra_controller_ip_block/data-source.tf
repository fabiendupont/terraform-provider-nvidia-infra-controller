data "nvidia_infra_controller_ip_block" "example" {
  id = "resource-uuid"
}

output "ip_block_name" {
  value = data.nvidia_infra_controller_ip_block.example.name
}
