data "nico_vpc_peering" "example" {
  id = "resource-uuid"
}

output "vpc_peering_name" {
  value = data.nico_vpc_peering.example.name
}
