resource "nico_instance_type" "example" {
  site_id                        = "site-id-uuid"
  machine_ids                    = []
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
