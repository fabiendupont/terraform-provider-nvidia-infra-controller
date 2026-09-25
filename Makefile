# SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
# SPDX-License-Identifier: Apache-2.0

SPEC_REPO := dsx-ai-factory/infra-controller
SPEC_REF  ?= v2.0.0-pr
SPEC_URL  := https://raw.githubusercontent.com/$(SPEC_REPO)/$(SPEC_REF)/rest-api/openapi/spec.yaml
SPEC_DIR  := .spec
SPEC      := $(SPEC_DIR)/spec.yaml

PROVIDER_DIR := internal/provider

.PHONY: fetch-spec generate build lint test clean

fetch-spec:
	mkdir -p $(SPEC_DIR)
	curl -sf -o $(SPEC) $(SPEC_URL)

generate: fetch-spec
	python scripts/generate.py --spec $(SPEC) --output $(PROVIDER_DIR)
	go fmt ./$(PROVIDER_DIR)/...
	tfplugindocs generate --provider-name nico

build: generate
	go build -v ./...

lint:
	golangci-lint run ./...

test:
	go test -v -count=1 -timeout 120s ./...

clean:
	rm -f $(PROVIDER_DIR)/resource_*.go
	rm -f $(PROVIDER_DIR)/data_source_*.go
	rm -f $(PROVIDER_DIR)/resources_registry.go
	find . -name '*.pyc' -delete 2>/dev/null || true
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
