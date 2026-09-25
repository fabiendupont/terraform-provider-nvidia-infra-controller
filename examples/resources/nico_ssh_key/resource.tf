resource "nico_ssh_key" "example" {
  ssh_key_group_id               = "ssh-key-group-id-uuid"
  name                           = "name-value"
  public_key                     = "public-key-value"
}
