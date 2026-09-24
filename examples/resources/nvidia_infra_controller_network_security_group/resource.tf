resource "nvidia_infra_controller_network_security_group" "example" {
  name                           = "name-value"
  site_id                        = "site-id-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
