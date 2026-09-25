resource "nico_ip_block" "example" {
  site_id                        = "site-id-uuid"
  name                           = "name-value"
  routing_type                   = "routing-type-value"
  prefix                         = "prefix-value"
  prefix_length                  = 0
  protocol_version               = "protocol-version-value"
  description                    = "description-value"
}
