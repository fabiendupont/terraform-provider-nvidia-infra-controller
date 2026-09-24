data "nvidia_infra_controller_measured_boot_trusted_profile" "example" {
  id = "resource-uuid"
}

output "measured_boot_trusted_profile_name" {
  value = data.nvidia_infra_controller_measured_boot_trusted_profile.example.name
}
