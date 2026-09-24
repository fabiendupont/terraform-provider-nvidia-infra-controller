# SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
# SPDX-License-Identifier: Apache-2.0

terraform {
  required_providers {
    nvidia-infra-controller = {
      source  = "fabiendupont/nvidia-infra-controller"
      version = "~> 2.0"
    }
  }
}

provider "nvidia-infra-controller" {
  # endpoint = "https://nico-rest-api.example.com"  # or NICO_ENDPOINT env var
  # token    = "your-bearer-token"                  # or NICO_TOKEN env var
  # org      = "your-org-name"                      # or NICO_ORG env var
}
