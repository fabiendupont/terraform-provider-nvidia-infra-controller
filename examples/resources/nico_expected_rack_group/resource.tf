resource "nico_expected_rack_group" "example" {
  site_id                        = "site-id-value"
  rack_group_id                  = "rack-group-id-value"
  topology                       = "topology-value"
  protocol                       = "protocol-value"
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
