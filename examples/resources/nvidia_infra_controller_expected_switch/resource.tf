resource "nvidia_infra_controller_expected_switch" "example" {
  site_id                        = "site-id-value"
  bmc_mac_address                = "bmc-mac-address-value"
  switch_serial_number           = "switch-serial-number-value"
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
