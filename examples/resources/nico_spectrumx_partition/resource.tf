resource "nico_spectrumx_partition" "example" {
  name                           = "name-value"
  site_id                        = "site-id-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
