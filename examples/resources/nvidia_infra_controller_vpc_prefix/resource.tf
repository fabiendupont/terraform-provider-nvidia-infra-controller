resource "nvidia_infra_controller_vpc_prefix" "example" {
  vpc_id                         = "vpc-id-uuid"
  site_id                        = "site-id-uuid"
  name                           = "name-value"
  ip_block_id                    = "ip-block-id-value"
  prefix_length                  = 0
}
