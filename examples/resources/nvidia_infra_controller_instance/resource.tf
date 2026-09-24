resource "nvidia_infra_controller_instance" "example" {
  name_prefix                    = "name-prefix-value"
  count                          = 0
  tenant_id                      = "tenant-id-value"
  instance_type_id               = "instance-type-id-value"
  vpc_id                         = "vpc-id-value"
  name                           = "name-value"
  description                    = "description-value"
  labels                         = {
    key = "value"
  }
}
