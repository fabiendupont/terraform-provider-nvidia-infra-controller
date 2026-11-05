resource "nico_subnet" "example" {
  vpc_id                         = "vpc-id-uuid"
  site_id                        = "site-id-uuid"
  name                           = "name-value"
  prefix_length                  = 0
  description                    = "description-value"
}
