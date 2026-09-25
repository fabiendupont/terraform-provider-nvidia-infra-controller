data "nico_dpu_machine" "example" {
  id = "resource-uuid"
}

output "dpu_machine_name" {
  value = data.nico_dpu_machine.example.name
}
