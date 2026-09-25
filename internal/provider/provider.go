// SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
// SPDX-License-Identifier: Apache-2.0

package provider

import (
	"context"
	"net/http"
	"os"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/function"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/provider/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ provider.Provider = &NicoProvider{}

// NicoProvider implements the NVIDIA Infra Controller Terraform provider.
type NicoProvider struct {
	version string
}

type NicoProviderModel struct {
	Endpoint types.String `tfsdk:"endpoint"`
	Token    types.String `tfsdk:"token"`
	Org      types.String `tfsdk:"org"`
}

func New(version string) func() provider.Provider {
	return func() provider.Provider {
		return &NicoProvider{version: version}
	}
}

func (p *NicoProvider) Metadata(_ context.Context, _ provider.MetadataRequest, resp *provider.MetadataResponse) {
	resp.TypeName = "nico"
	resp.Version = p.version
}

func (p *NicoProvider) Schema(_ context.Context, _ provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Provider for the NVIDIA Infra Controller (NICo) REST API.",
		Attributes: map[string]schema.Attribute{
			"endpoint": schema.StringAttribute{
				Optional:    true,
				Description: "NICo REST API base URL. Falls back to NICO_ENDPOINT environment variable.",
			},
			"token": schema.StringAttribute{
				Optional:    true,
				Sensitive:   true,
				Description: "Bearer token for authentication. Falls back to NICO_TOKEN environment variable.",
			},
			"org": schema.StringAttribute{
				Optional:    true,
				Description: "Organization name used in API paths. Falls back to NICO_ORG environment variable.",
			},
		},
	}
}

func (p *NicoProvider) Configure(ctx context.Context, req provider.ConfigureRequest, resp *provider.ConfigureResponse) {
	var config NicoProviderModel
	resp.Diagnostics.Append(req.Config.Get(ctx, &config)...)
	if resp.Diagnostics.HasError() {
		return
	}

	endpoint := os.Getenv("NICO_ENDPOINT")
	if !config.Endpoint.IsNull() && !config.Endpoint.IsUnknown() {
		endpoint = config.Endpoint.ValueString()
	}

	token := os.Getenv("NICO_TOKEN")
	if !config.Token.IsNull() && !config.Token.IsUnknown() {
		token = config.Token.ValueString()
	}

	org := os.Getenv("NICO_ORG")
	if !config.Org.IsNull() && !config.Org.IsUnknown() {
		org = config.Org.ValueString()
	}

	if endpoint == "" {
		resp.Diagnostics.AddError("Missing endpoint", "Set endpoint in provider config or NICO_ENDPOINT env var.")
		return
	}
	if token == "" {
		resp.Diagnostics.AddError("Missing token", "Set token in provider config or NICO_TOKEN env var.")
		return
	}
	if org == "" {
		resp.Diagnostics.AddError("Missing org", "Set org in provider config or NICO_ORG env var.")
		return
	}

	client := &Client{
		BaseURL:    endpoint,
		Org:        org,
		Token:      token,
		HTTPClient: &http.Client{},
	}

	resp.DataSourceData = client
	resp.ResourceData = client
}

func (p *NicoProvider) Resources(_ context.Context) []func() resource.Resource {
	return providerResources()
}

func (p *NicoProvider) DataSources(_ context.Context) []func() datasource.DataSource {
	return providerDataSources()
}

func (p *NicoProvider) Functions(_ context.Context) []func() function.Function {
	return nil
}
