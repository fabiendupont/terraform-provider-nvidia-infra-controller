// SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
// SPDX-License-Identifier: Apache-2.0

package provider

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/hashicorp/terraform-plugin-framework/types"
)

// Client is the HTTP client for the NICo REST API.
type Client struct {
	BaseURL    string
	Org        string
	Token      string
	HTTPClient *http.Client
}

// ResolvePath substitutes {org} and other path parameters, then prepends BaseURL.
func (c *Client) ResolvePath(path string, params map[string]string) string {
	result := strings.ReplaceAll(path, "{org}", c.Org)
	for k, v := range params {
		result = strings.ReplaceAll(result, "{"+k+"}", v)
	}
	return strings.TrimRight(c.BaseURL, "/") + result
}

func (c *Client) headers() map[string]string {
	return map[string]string{
		"Authorization": "Bearer " + c.Token,
		"Accept":        "application/json",
		"Content-Type":  "application/json",
	}
}

func (c *Client) doRequest(ctx context.Context, method, fullURL string, body interface{}) (map[string]interface{}, int, error) {
	var bodyReader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, 0, fmt.Errorf("marshaling request body: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, fullURL, bodyReader)
	if err != nil {
		return nil, 0, fmt.Errorf("creating request: %w", err)
	}

	for k, v := range c.headers() {
		req.Header.Set(k, v)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("executing request %s %s: %w", method, fullURL, err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("reading response body: %w", err)
	}

	if resp.StatusCode == 404 {
		return nil, 404, nil
	}
	if resp.StatusCode >= 400 {
		return nil, resp.StatusCode, fmt.Errorf("API error %d: %s", resp.StatusCode, string(respBody))
	}
	if resp.StatusCode == 204 || len(respBody) == 0 {
		return nil, resp.StatusCode, nil
	}

	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, resp.StatusCode, fmt.Errorf("parsing response: %w", err)
	}
	return result, resp.StatusCode, nil
}

// Get fetches a single resource. Returns nil, nil on 404.
func (c *Client) Get(ctx context.Context, fullURL string) (map[string]interface{}, error) {
	result, _, err := c.doRequest(ctx, http.MethodGet, fullURL, nil)
	return result, err
}

// List fetches all pages of a collection.
func (c *Client) List(ctx context.Context, fullURL string, queryParams map[string]string) ([]map[string]interface{}, error) {
	var results []map[string]interface{}
	page := 1
	pageSize := 100

	for {
		u, err := url.Parse(fullURL)
		if err != nil {
			return nil, fmt.Errorf("parsing URL: %w", err)
		}
		q := u.Query()
		for k, v := range queryParams {
			if v != "" {
				q.Set(k, v)
			}
		}
		q.Set("pageNumber", strconv.Itoa(page))
		q.Set("pageSize", strconv.Itoa(pageSize))
		u.RawQuery = q.Encode()

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
		if err != nil {
			return nil, fmt.Errorf("creating list request: %w", err)
		}
		for k, v := range c.headers() {
			req.Header.Set(k, v)
		}

		resp, err := c.HTTPClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("executing list request: %w", err)
		}

		respBody, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return nil, fmt.Errorf("reading list response: %w", err)
		}
		if resp.StatusCode >= 400 {
			return nil, fmt.Errorf("API list error %d: %s", resp.StatusCode, string(respBody))
		}

		var items []map[string]interface{}
		if err := json.Unmarshal(respBody, &items); err != nil {
			// Try wrapped response format {"items": [...]}
			var wrapped map[string]interface{}
			if err2 := json.Unmarshal(respBody, &wrapped); err2 == nil {
				if raw, ok := wrapped["items"]; ok {
					if slice, ok := raw.([]interface{}); ok {
						for _, item := range slice {
							if m, ok := item.(map[string]interface{}); ok {
								items = append(items, m)
							}
						}
					}
				}
			}
		}
		results = append(results, items...)

		// Parse X-Pagination header to determine if more pages exist.
		paginationHeader := resp.Header.Get("X-Pagination")
		if paginationHeader == "" {
			break
		}
		var pagination map[string]interface{}
		if err := json.Unmarshal([]byte(paginationHeader), &pagination); err != nil {
			break
		}
		total := int(pagination["total"].(float64))
		if page*pageSize >= total {
			break
		}
		page++
	}

	return results, nil
}

// Post creates a resource and returns the created object.
func (c *Client) Post(ctx context.Context, fullURL string, body interface{}) (map[string]interface{}, error) {
	result, _, err := c.doRequest(ctx, http.MethodPost, fullURL, body)
	return result, err
}

// Patch updates a resource and returns the updated object.
func (c *Client) Patch(ctx context.Context, fullURL string, body interface{}) (map[string]interface{}, error) {
	result, _, err := c.doRequest(ctx, http.MethodPatch, fullURL, body)
	return result, err
}

// Delete removes a resource. body is optional (some resources allow a delete body).
func (c *Client) Delete(ctx context.Context, fullURL string, body interface{}) error {
	_, _, err := c.doRequest(ctx, http.MethodDelete, fullURL, body)
	return err
}

// ---------------------------------------------------------------------------
// Type conversion helpers used by generated resource and data source files.
// ---------------------------------------------------------------------------

func StringFromAPI(v interface{}) types.String {
	if v == nil {
		return types.StringNull()
	}
	s, ok := v.(string)
	if !ok {
		return types.StringNull()
	}
	return types.StringValue(s)
}

func Int64FromAPI(v interface{}) types.Int64 {
	if v == nil {
		return types.Int64Null()
	}
	f, ok := v.(float64)
	if !ok {
		return types.Int64Null()
	}
	return types.Int64Value(int64(f))
}

func BoolFromAPI(v interface{}) types.Bool {
	if v == nil {
		return types.BoolNull()
	}
	b, ok := v.(bool)
	if !ok {
		return types.BoolNull()
	}
	return types.BoolValue(b)
}

func Float64FromAPI(v interface{}) types.Float64 {
	if v == nil {
		return types.Float64Null()
	}
	f, ok := v.(float64)
	if !ok {
		return types.Float64Null()
	}
	return types.Float64Value(f)
}

// StringSliceFromAPI converts []interface{} to []string.
func StringSliceFromAPI(v interface{}) []string {
	if v == nil {
		return nil
	}
	raw, ok := v.([]interface{})
	if !ok {
		return nil
	}
	result := make([]string, 0, len(raw))
	for _, item := range raw {
		if s, ok := item.(string); ok {
			result = append(result, s)
		}
	}
	return result
}

// StringMapFromAPI converts map[string]interface{} to map[string]string.
func StringMapFromAPI(v interface{}) map[string]string {
	if v == nil {
		return nil
	}
	raw, ok := v.(map[string]interface{})
	if !ok {
		return nil
	}
	result := make(map[string]string, len(raw))
	for k, mv := range raw {
		if s, ok := mv.(string); ok {
			result[k] = s
		}
	}
	return result
}
