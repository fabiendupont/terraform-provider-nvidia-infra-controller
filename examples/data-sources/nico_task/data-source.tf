data "nico_task" "example" {
  id = "resource-uuid"
}

output "task_name" {
  value = data.nico_task.example.name
}
