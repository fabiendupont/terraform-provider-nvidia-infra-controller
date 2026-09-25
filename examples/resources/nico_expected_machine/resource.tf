resource "nico_expected_machine" "example" {
  site_id                        = "site-id-uuid"
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
