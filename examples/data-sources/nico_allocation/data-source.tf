data "nico_allocation" "example" {
  id = "resource-uuid"
}

output "allocation_name" {
  value = data.nico_allocation.example.name
}
