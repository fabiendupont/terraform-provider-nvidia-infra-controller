data "nvidia_infra_controller_task_run" "example" {
  id = "resource-uuid"
}

output "task_run_name" {
  value = data.nvidia_infra_controller_task_run.example.name
}
