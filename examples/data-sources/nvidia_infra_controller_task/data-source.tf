data "nvidia_infra_controller_task" "example" {
  id = "resource-uuid"
}

output "task_name" {
  value = data.nvidia_infra_controller_task.example.name
}
