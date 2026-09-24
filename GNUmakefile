# SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
# SPDX-License-Identifier: Apache-2.0

default: build

.PHONY: build
build:
	go build -v ./...

.PHONY: generate
generate:
	go generate ./...

.PHONY: fmt
fmt:
	gofmt -s -w .

.PHONY: lint
lint:
	golangci-lint run ./...

.PHONY: test
test:
	go test -v -count=1 -timeout 120s ./...

.PHONY: testacc
testacc:
	TF_ACC=1 go test -v -count=1 -timeout 600s ./internal/provider/...

.PHONY: tidy
tidy:
	go mod tidy

.PHONY: docs
docs:
	go generate ./...
	tfplugindocs generate --provider-name nvidia-infra-controller

.PHONY: clean
clean:
	rm -f terraform-provider-nvidia-infra-controller
