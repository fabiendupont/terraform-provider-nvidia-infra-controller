data "nvidia_infra_controller_dpu_machine" "example" {
  id = "resource-uuid"
}

output "dpu_machine_name" {
  value = data.nvidia_infra_controller_dpu_machine.example.name
}
