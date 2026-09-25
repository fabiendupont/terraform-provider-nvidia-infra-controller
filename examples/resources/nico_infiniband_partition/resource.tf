resource "nico_infiniband_partition" "example" {
  site_id                        = "site-id-uuid"
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
