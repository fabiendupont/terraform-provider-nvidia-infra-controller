# Terraform Provider for NVIDIA Infra Controller

![Provider version](https://img.shields.io/badge/version-2.0.0-blue)
![Spec version](https://img.shields.io/badge/spec-2.0.0-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Terraform](https://img.shields.io/badge/terraform-%3E%3D1.0-purple)

The `nico` provider manages resources on
[NVIDIA Infra Controller](https://github.com/dsx-ai-factory/infra-controller) (NICo)
— GPU bare-metal provisioning, VPC networking, instance lifecycle, and more.
All resources and data sources are generated directly from the NICo OpenAPI
specification and track the upstream API version exactly.

**Use this provider to:**

- Provision and deprovision GPU bare-metal instances declaratively
- Manage VPCs, subnets, IP blocks, and VPC peerings as Terraform state
- Automate NICo resource lifecycle in GitOps and CI/CD pipelines

## Requirements

- Terraform >= 1.0
- A JWT bearer token for the Infra Controller API

## Installation

### From the Terraform Registry

```hcl
terraform {
  required_providers {
    nico = {
      source  = "fabiendupont/nvidia-infra-controller"
      version = "~> 2.0"
    }
  }
}
```

### Manual installation

Download the binary for your platform from the
[GitHub Releases](https://github.com/fabiendupont/terraform-provider-nvidia-infra-controller/releases)
page and place it in your
[Terraform plugin directory](https://developer.hashicorp.com/terraform/cli/config/config-file#provider-installation).

## Authentication

Configure the provider in your Terraform root module:

```hcl
provider "nico" {
  endpoint = "https://nico-rest-api.example.com"
  token    = var.nico_token
  org      = "my-org"
}
```

All three values can also be supplied via environment variables — useful in
CI/CD so secrets never appear in `.tf` files:

| Argument   | Environment Variable | Description                        |
|------------|----------------------|------------------------------------|
| `endpoint` | `NICO_ENDPOINT`      | Base URL of the NICo REST API      |
| `token`    | `NICO_TOKEN`         | JWT bearer token                   |
| `org`      | `NICO_ORG`           | Organization name used in API paths |

### Obtaining a token

Exchange SSA credentials for a JWT:

```bash
export NICO_TOKEN=$(curl -s -X POST "$SSA_TOKEN_URL" \
  -d "client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET&grant_type=client_credentials" \
  | jq -r '.access_token')
```

## Quick start

### Create a VPC and provision an instance

```hcl
resource "nico_vpc" "lab" {
  name                       = "lab-vpc"
  site_id                    = var.site_id
  network_virtualization_type = "FNN"
  labels = {
    env = "lab"
  }
}

resource "nico_ip_block" "lab" {
  site_id = var.site_id
  # ...
}

resource "nico_vpc_prefix" "lab" {
  name         = "lab-prefix"
  vpc_id       = nico_vpc.lab.id
  ip_block_id  = nico_ip_block.lab.id
  prefix_length = 24
}

resource "nico_instance" "gpu_worker" {
  name               = "gpu-worker-01"
  tenant_id          = var.tenant_id
  instance_type_id   = var.instance_type_id
  vpc_id             = nico_vpc.lab.id
  operating_system_id = var.os_id
  ssh_key_group_ids  = [var.ssh_key_group_id]
  labels = {
    env  = "lab"
    role = "worker"
  }
}
```

### Read existing resources

```hcl
data "nico_site" "main" {
  id = var.site_id
}

data "nico_vpc" "existing" {
  id = var.vpc_id
}

output "site_name" {
  value = data.nico_site.main.name
}
```

### Delete resources

Resources are destroyed with `terraform destroy` or by removing them from
configuration. The provider handles DELETE for all writable resources.

## Versioning

This provider tracks the upstream NICo API version. Each provider release
corresponds to a NICo API release:

| Provider version | NICo API version |
|-----------------|-----------------|
| 2.x.y           | v2.x.y          |

New NICo releases are automatically detected by the
[sync workflow](.github/workflows/sync.yml), which regenerates the provider,
creates a matching git tag, and publishes a GitHub Release.

## Regenerating from a new spec

To regenerate against a specific upstream NICo tag:

```bash
make generate SPEC_REF=v2.1.0
```

Or against a local spec file:

```bash
python scripts/generate.py --spec /path/to/spec.yaml --output internal/provider
go fmt ./internal/provider/...
go build ./...
```

## Development

### Building locally

```bash
go build -o terraform-provider-nvidia-infra-controller .
```

Install into your local Terraform plugin cache:

```bash
mkdir -p ~/.terraform.d/plugins/registry.terraform.io/fabiendupont/nvidia-infra-controller/0.0.1/linux_amd64
cp terraform-provider-nvidia-infra-controller ~/.terraform.d/plugins/registry.terraform.io/fabiendupont/nvidia-infra-controller/0.0.1/linux_amd64/
```

### Running tests

```bash
make test         # unit tests
make testacc      # acceptance tests (requires TF_ACC=1 and live NICo endpoint)
```

### Generating documentation

```bash
make docs
```

Requires [`tfplugindocs`](https://github.com/hashicorp/terraform-plugin-docs) to be installed.

## License

Apache-2.0. See [LICENSE](LICENSE).
