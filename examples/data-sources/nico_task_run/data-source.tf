data "nico_task_run" "example" {
  id = "resource-uuid"
}

output "task_run_name" {
  value = data.nico_task_run.example.name
}
