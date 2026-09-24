data "nvidia_infra_controller_measured_boot_trusted_machine" "example" {
  id = "resource-uuid"
}

output "measured_boot_trusted_machine_name" {
  value = data.nvidia_infra_controller_measured_boot_trusted_machine.example.name
}
