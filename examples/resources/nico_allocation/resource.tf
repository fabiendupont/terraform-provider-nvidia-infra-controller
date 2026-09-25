resource "nico_allocation" "example" {
  site_id                        = "site-id-uuid"
  name                           = "name-value"
  tenant_id                      = "tenant-id-value"
  constraint_value               = 0
  description                    = "description-value"
}
