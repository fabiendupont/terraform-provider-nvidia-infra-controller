resource "nico_expected_power_shelf" "example" {
  site_id                        = "site-id-value"
  bmc_mac_address                = "bmc-mac-address-value"
  shelf_serial_number            = "shelf-serial-number-value"
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
