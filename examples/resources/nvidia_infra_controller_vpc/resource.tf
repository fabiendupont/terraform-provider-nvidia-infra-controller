resource "nvidia_infra_controller_vpc" "example" {
  site_id                        = "site-id-uuid"
  if_version_match               = "if-version-match-value"
  expected_inactive_vni          = 0
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
