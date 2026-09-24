#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
# SPDX-License-Identifier: Apache-2.0

"""Generate Terraform provider Go files from the NVIDIA Infra Controller OpenAPI spec.

Usage:
    python scripts/generate.py --spec .spec/spec.yaml --output internal/provider
"""

import argparse
import os
import re
import sys

import yaml


def safe_format(template, **kwargs):
    """Substitute {key} placeholders without interpreting Go-style {} braces.

    Unlike str.format(), values are inserted literally — braces inside values
    are not re-processed. After substitution, {{ and }} in the template are
    converted to single { and }.
    """
    result = template
    for k in sorted(kwargs.keys(), key=lambda x: -len(x)):
        result = result.replace('{' + k + '}', str(kwargs[k]))
    result = result.replace('{{', '{').replace('}}', '}')
    return result

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resource_config import (
    RESOURCE_OVERRIDES,
    READ_ONLY_TAGS,
    SKIP_TAGS,
    TAG_TO_RESOURCE,
    SKIP_PATHS,
)

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

_PATH_PARAM_RE = re.compile(r'\{(\w+)\}')


def camel_to_snake(name):
    s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()


def snake_to_pascal(name):
    return ''.join(word.capitalize() for word in name.split('_'))


def tag_to_resource_name(tag):
    if tag in TAG_TO_RESOURCE:
        return TAG_TO_RESOURCE[tag]
    return camel_to_snake(tag.replace(' ', ''))


def resolve_ref(spec, ref):
    if not ref.startswith('#/'):
        return {}
    parts = ref.lstrip('#/').split('/')
    obj = spec
    for part in parts:
        obj = obj.get(part, {}) if isinstance(obj, dict) else {}
    return obj


def resolve_refs_recursive(spec, obj, depth=0):
    if depth > 20:
        return obj
    if isinstance(obj, dict):
        if '$ref' in obj:
            referenced = resolve_ref(spec, obj['$ref'])
            merged = dict(resolve_refs_recursive(spec, referenced, depth + 1))
            for k, v in obj.items():
                if k != '$ref':
                    merged[k] = v
            return merged
        return {k: resolve_refs_recursive(spec, v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_refs_recursive(spec, item, depth + 1) for item in obj]
    return obj


def get_schema_type(schema):
    """Get the effective type from an OpenAPI schema, handling 3.1 type arrays."""
    t = schema.get('type', 'string')
    if isinstance(t, list):
        non_null = [x for x in t if x != 'null']
        return non_null[0] if non_null else 'string'
    return t


# ---------------------------------------------------------------------------
# Path analysis (mirrors the Ansible generator)
# ---------------------------------------------------------------------------

def classify_path(path):
    last = path.rstrip('/').split('/')[-1]
    return 'item' if (last.startswith('{') and last.endswith('}')) else 'collection'


def extract_id_param(path):
    last = path.rstrip('/').split('/')[-1]
    if last.startswith('{') and last.endswith('}'):
        return last[1:-1]
    return None


def detect_nested_resource_name(path):
    prefix = '/v2/org/{org}/carbide/'
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix):]
    segments = rest.split('/')
    parts = [s for s in segments if not s.startswith('{') and s != 'current']
    if len(parts) >= 2:
        return '_'.join(camel_to_snake(p).replace('-', '_') for p in parts)
    return None


def group_paths_by_tag(spec):
    groups = {}
    paths = spec.get('paths', {})

    for path, path_item in paths.items():
        if path in SKIP_PATHS:
            continue

        for method in ('get', 'post', 'patch', 'put', 'delete'):
            operation = path_item.get(method)
            if not operation:
                continue

            tags = operation.get('tags', [])
            if not tags:
                continue

            tag = tags[0]
            if tag in SKIP_TAGS:
                continue

            base_name = tag_to_resource_name(tag)
            nested_name = detect_nested_resource_name(path)

            if nested_name and nested_name != base_name:
                group_key = nested_name
                if group_key not in groups:
                    groups[group_key] = {'operations': [], 'tag': tag, 'resource_name': nested_name}
            else:
                group_key = tag
                if group_key not in groups:
                    groups[group_key] = {'operations': [], 'tag': tag, 'resource_name': base_name}

            groups[group_key]['operations'].append({
                'method': method.upper(),
                'path': path,
                'path_type': classify_path(path),
                'operation': operation,
                'id_param': extract_id_param(path),
            })

    return groups


# Terraform meta-argument names that cannot be used as resource attribute names.
_RESERVED_TF_NAMES = frozenset({
    'count', 'depends_on', 'for_each', 'lifecycle',
    'provider', 'provisioner', 'connection',
})


def safe_tf_name(name):
    """Append _value to any name that clashes with a Terraform meta-argument."""
    return (name + '_value') if name in _RESERVED_TF_NAMES else name


# ---------------------------------------------------------------------------
# Resource analysis
# ---------------------------------------------------------------------------

def analyze_resource(tag, group, spec):
    resource_name = group['resource_name']
    operations = group['operations']
    is_read_only = tag in READ_ONLY_TAGS

    info = {
        'resource_name': resource_name,
        'tag': tag,
        'is_read_only': is_read_only,
        'collection_path': None,
        'item_path': None,
        'id_param': None,
        'has_create': False,
        'has_update': False,
        'has_delete': False,
        'has_list': False,
        'has_get': False,
        'create_schema': None,
        'update_schema': None,
        'delete_schema': None,
        'response_schema': None,
        'list_query_params': [],
        'description': '',
    }

    for op in operations:
        method = op['method']
        path = op['path']
        path_type = op['path_type']
        operation = op['operation']

        if not info['description']:
            for t in spec.get('tags', []):
                if t.get('name') == tag:
                    info['description'] = t.get('description', '').split('\n\n')[0].strip()
                    break

        if path_type == 'collection':
            info['collection_path'] = path
            if method == 'GET':
                info['has_list'] = True
                seen_qp = {p.get('name') for p in info['list_query_params']}
                for param in operation.get('parameters', []):
                    if param.get('in') == 'query' and param.get('name') not in (
                        'pageNumber', 'pageSize', 'orderBy', 'includeRelation',
                    ) and param.get('name') not in seen_qp:
                        info['list_query_params'].append(param)
                        seen_qp.add(param.get('name'))
            elif method == 'POST':
                info['has_create'] = True
                body = operation.get('requestBody', {})
                schema = body.get('content', {}).get('application/json', {}).get('schema', {})
                if '$ref' in schema:
                    schema = resolve_refs_recursive(spec, schema)
                info['create_schema'] = schema
        elif path_type == 'item':
            info['item_path'] = path
            info['id_param'] = op['id_param']
            if method == 'GET':
                info['has_get'] = True
                resp = operation.get('responses', {}).get('200', {})
                schema = resp.get('content', {}).get('application/json', {}).get('schema', {})
                if '$ref' in schema:
                    schema = resolve_refs_recursive(spec, schema)
                info['response_schema'] = schema
            elif method in ('PATCH', 'PUT'):
                info['has_update'] = True
                body = operation.get('requestBody', {})
                schema = body.get('content', {}).get('application/json', {}).get('schema', {})
                if '$ref' in schema:
                    schema = resolve_refs_recursive(spec, schema)
                info['update_schema'] = schema
            elif method == 'DELETE':
                info['has_delete'] = True
                body = operation.get('requestBody', {})
                if body:
                    schema = body.get('content', {}).get('application/json', {}).get('schema', {})
                    if '$ref' in schema:
                        schema = resolve_refs_recursive(spec, schema)
                    info['delete_schema'] = schema

    # Fallback: get response schema from list endpoint
    if not info['response_schema'] and info['has_list']:
        for op in operations:
            if op['method'] == 'GET' and op['path_type'] == 'collection':
                resp = op['operation'].get('responses', {}).get('200', {})
                schema = resp.get('content', {}).get('application/json', {}).get('schema', {})
                if schema.get('type') == 'array':
                    items = schema.get('items', {})
                    if '$ref' in items:
                        items = resolve_refs_recursive(spec, items)
                    info['response_schema'] = items
                elif '$ref' in schema:
                    info['response_schema'] = resolve_refs_recursive(spec, schema)
                break

    # Handle singleton endpoints (current)
    if not info['item_path'] and not info['collection_path']:
        for op in operations:
            if op['method'] == 'GET':
                info['collection_path'] = op['path']
                info['has_list'] = True
                resp = op['operation'].get('responses', {}).get('200', {})
                schema = resp.get('content', {}).get('application/json', {}).get('schema', {})
                if '$ref' in schema:
                    schema = resolve_refs_recursive(spec, schema)
                info['response_schema'] = schema
                break

    return info


# ---------------------------------------------------------------------------
# Field analysis: OpenAPI schema -> Terraform field descriptors
# ---------------------------------------------------------------------------

# Terraform meta-argument names that cannot be used as resource attribute names.
_RESERVED_TF_NAMES = frozenset({
    'count', 'depends_on', 'for_each', 'lifecycle',
    'provider', 'provisioner', 'connection',
})


def analyze_field(prop_name, prop_schema, spec, resource_pascal, required_fields):
    """Return a field descriptor dict for one OpenAPI property."""
    snake_name = safe_tf_name(camel_to_snake(prop_name))
    pascal_name = snake_to_pascal(snake_name)
    schema_type = get_schema_type(prop_schema)
    description = prop_schema.get('description', '%s attribute.' % snake_name).replace('\n', ' ').replace('\r', ' ')

    base = {
        'snake_name': snake_name,
        'pascal_name': pascal_name,
        'json_name': prop_name,
        'required': prop_name in required_fields,
        'read_only': prop_schema.get('readOnly', False),
        'description': description,
        'enum': prop_schema.get('enum'),
        'sub_fields': [],
        'nested_type_name': None,
        'element_go_type': None,
        'tf_attr_type': None,
        'go_type': None,
    }

    if schema_type == 'string':
        base.update({'go_type': 'types.String', 'tf_attr_type': 'string'})
    elif schema_type == 'integer':
        base.update({'go_type': 'types.Int64', 'tf_attr_type': 'int64'})
    elif schema_type == 'boolean':
        base.update({'go_type': 'types.Bool', 'tf_attr_type': 'bool'})
    elif schema_type == 'number':
        base.update({'go_type': 'types.Float64', 'tf_attr_type': 'float64'})
    elif schema_type == 'object' and 'additionalProperties' in prop_schema:
        base.update({'go_type': 'types.Map', 'tf_attr_type': 'map_string'})
    elif schema_type == 'object' and 'properties' in prop_schema:
        nested_name = resource_pascal + pascal_name
        sub_fields = analyze_schema_fields(prop_schema, spec, nested_name)
        base.update({
            'go_type': '*' + nested_name,
            'tf_attr_type': 'single_nested',
            'nested_type_name': nested_name,
            'sub_fields': sub_fields,
        })
    elif schema_type == 'array':
        items_schema = prop_schema.get('items', {})
        if '$ref' in items_schema:
            items_schema = resolve_refs_recursive(spec, items_schema)
        items_type = get_schema_type(items_schema)

        if items_type == 'string':
            base.update({'go_type': 'types.List', 'tf_attr_type': 'list_string', 'element_go_type': 'types.StringType'})
        elif items_type == 'integer':
            base.update({'go_type': 'types.List', 'tf_attr_type': 'list_int64', 'element_go_type': 'types.Int64Type'})
        elif items_type == 'boolean':
            base.update({'go_type': 'types.List', 'tf_attr_type': 'list_bool', 'element_go_type': 'types.BoolType'})
        elif items_type in ('object',) or 'properties' in items_schema:
            nested_name = resource_pascal + pascal_name + 'Item'
            sub_fields = analyze_schema_fields(items_schema, spec, nested_name)
            base.update({
                'go_type': '[]' + nested_name,
                'tf_attr_type': 'list_nested',
                'nested_type_name': nested_name,
                'sub_fields': sub_fields,
            })
        else:
            base.update({'go_type': 'types.List', 'tf_attr_type': 'list_string', 'element_go_type': 'types.StringType'})
    else:
        base.update({'go_type': 'types.String', 'tf_attr_type': 'string'})

    return base


def analyze_schema_fields(schema, spec, resource_pascal):
    """Return a list of field descriptors for an OpenAPI object schema."""
    if not schema or 'properties' not in schema:
        return []
    required_fields = schema.get('required', [])
    fields = []
    for prop_name, prop_schema in schema.get('properties', {}).items():
        field = analyze_field(prop_name, prop_schema, spec, resource_pascal, required_fields)
        fields.append(field)
    return fields


def merge_resource_fields(resource_info, spec):
    """Build a unified field set from create, update, and response schemas.

    Returns a list of field dicts with added 'in_create', 'in_update', 'in_response' flags.
    Also returns a set of path param names that need to be added separately.
    """
    resource_name = resource_info['resource_name']
    resource_pascal = snake_to_pascal(resource_name)

    field_map = {}  # snake_name -> field dict

    def add_fields(schema, flag):
        if not schema or 'properties' not in schema:
            return
        required_fields = schema.get('required', [])
        for prop_name, prop_schema in schema.get('properties', {}).items():
            snake_name = camel_to_snake(prop_name)
            if snake_name not in field_map:
                f = analyze_field(prop_name, prop_schema, spec, resource_pascal, required_fields)
                f['in_create'] = False
                f['in_update'] = False
                f['in_response'] = False
                field_map[snake_name] = f
            # Track which schemas contain this field
            field_map[snake_name][flag] = True
            # If required in create schema, mark as required
            if flag == 'in_create' and prop_name in required_fields:
                field_map[snake_name]['required'] = True

    add_fields(resource_info.get('create_schema'), 'in_create')
    add_fields(resource_info.get('update_schema'), 'in_update')
    add_fields(resource_info.get('response_schema'), 'in_response')

    # Detect path parameters (e.g., {vpcId}) that need to be added
    path_params = set()
    for path in (resource_info.get('collection_path') or '', resource_info.get('item_path') or ''):
        for match in _PATH_PARAM_RE.findall(path):
            if match != 'org':
                path_params.add(safe_tf_name(camel_to_snake(match)))

    return list(field_map.values()), path_params


# ---------------------------------------------------------------------------
# Go code generation helpers
# ---------------------------------------------------------------------------

def indent(text, n=1):
    prefix = '\t' * n
    return '\n'.join(prefix + line if line.strip() else line for line in text.split('\n'))


def go_struct_field(field):
    """Return one Go struct field line."""
    return '\t%s %s `tfsdk:"%s"`' % (field['pascal_name'], field['go_type'], field['snake_name'])


def go_nested_structs(fields, depth=0):
    """Recursively generate nested Go struct definitions."""
    lines = []
    for f in fields:
        if f['tf_attr_type'] in ('list_nested', 'single_nested') and f['sub_fields']:
            type_name = f['nested_type_name']
            lines.append('type %s struct {' % type_name)
            for sf in f['sub_fields']:
                lines.append(go_struct_field(sf))
            lines.append('}')
            lines.append('')
            # Recurse into sub-fields
            lines.extend(go_nested_structs(f['sub_fields'], depth + 1))
    return lines


def go_schema_attribute(field, required=False, optional=False, computed=False):
    """Return Go schema attribute definition lines for a field."""
    desc = field['description'].replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
    req_str = 'true' if required else 'false'
    opt_str = 'true' if optional else 'false'
    comp_str = 'true' if computed else 'false'

    t = field['tf_attr_type']

    if t in ('string', 'int64', 'bool', 'float64'):
        attr_type = {'string': 'schema.StringAttribute', 'int64': 'schema.Int64Attribute',
                     'bool': 'schema.BoolAttribute', 'float64': 'schema.Float64Attribute'}[t]
        return [
            '"%s": %s{' % (field['snake_name'], attr_type),
            '\tRequired:    %s,' % req_str,
            '\tOptional:    %s,' % opt_str,
            '\tComputed:    %s,' % comp_str,
            '\tDescription: "%s",' % desc,
            '},',
        ]
    elif t == 'map_string':
        return [
            '"%s": schema.MapAttribute{' % field['snake_name'],
            '\tElementType: types.StringType,',
            '\tRequired:    %s,' % req_str,
            '\tOptional:    %s,' % opt_str,
            '\tComputed:    %s,' % comp_str,
            '\tDescription: "%s",' % desc,
            '},',
        ]
    elif t in ('list_string', 'list_int64', 'list_bool'):
        elem_type = field['element_go_type'] or 'types.StringType'
        return [
            '"%s": schema.ListAttribute{' % field['snake_name'],
            '\tElementType: %s,' % elem_type,
            '\tRequired:    %s,' % req_str,
            '\tOptional:    %s,' % opt_str,
            '\tComputed:    %s,' % comp_str,
            '\tDescription: "%s",' % desc,
            '},',
        ]
    elif t == 'list_nested':
        nested_attrs = go_schema_attrs_block(field['sub_fields'], computed_only=computed)
        lines = [
            '"%s": schema.ListNestedAttribute{' % field['snake_name'],
            '\tRequired:    %s,' % req_str,
            '\tOptional:    %s,' % opt_str,
            '\tComputed:    %s,' % comp_str,
            '\tDescription: "%s",' % desc,
            '\tNestedObject: schema.NestedAttributeObject{',
            '\t\tAttributes: map[string]schema.Attribute{',
        ]
        for line in nested_attrs:
            lines.append('\t\t\t' + line)
        lines += [
            '\t\t},',
            '\t},',
            '},',
        ]
        return lines
    elif t == 'single_nested':
        nested_attrs = go_schema_attrs_block(field['sub_fields'], computed_only=computed)
        lines = [
            '"%s": schema.SingleNestedAttribute{' % field['snake_name'],
            '\tRequired:    %s,' % req_str,
            '\tOptional:    %s,' % opt_str,
            '\tComputed:    %s,' % comp_str,
            '\tDescription: "%s",' % desc,
            '\tAttributes: map[string]schema.Attribute{',
        ]
        for line in nested_attrs:
            lines.append('\t\t' + line)
        lines += [
            '\t},',
            '},',
        ]
        return lines
    else:
        return [
            '"%s": schema.StringAttribute{' % field['snake_name'],
            '\tOptional: true,',
            '\tComputed: true,',
            '\tDescription: "%s",' % desc,
            '},',
        ]


def go_schema_attrs_block(fields, computed_only=False):
    """Generate a flat list of attribute lines (without the outer map wrapper)."""
    lines = []
    for f in fields:
        if f['read_only'] or computed_only:
            attr_lines = go_schema_attribute(f, required=False, optional=False, computed=True)
        elif f['required']:
            attr_lines = go_schema_attribute(f, required=True, optional=False, computed=False)
        else:
            attr_lines = go_schema_attribute(f, required=False, optional=True, computed=True)
        lines.extend(attr_lines)
    return lines


def go_populate_model_field(field, source_var='result'):
    """Generate Go code to populate one model field from an API result map."""
    t = field['tf_attr_type']
    sn = field['snake_name']
    pn = field['pascal_name']
    jn = field['json_name']

    if t == 'string':
        return ['data.%s = StringFromAPI(%s["%s"])' % (pn, source_var, jn)]
    elif t == 'int64':
        return ['data.%s = Int64FromAPI(%s["%s"])' % (pn, source_var, jn)]
    elif t == 'bool':
        return ['data.%s = BoolFromAPI(%s["%s"])' % (pn, source_var, jn)]
    elif t == 'float64':
        return ['data.%s = Float64FromAPI(%s["%s"])' % (pn, source_var, jn)]
    elif t == 'map_string':
        lines = [
            'if rawMap_%s := StringMapFromAPI(%s["%s"]); rawMap_%s != nil {' % (sn, source_var, jn, sn),
            '\tmv, d := types.MapValueFrom(ctx, types.StringType, rawMap_%s)' % sn,
            '\tdiags.Append(d...)',
            '\tdata.%s = mv' % pn,
            '} else {',
            '\tdata.%s = types.MapNull(types.StringType)' % pn,
            '}',
        ]
        return lines
    elif t in ('list_string', 'list_int64', 'list_bool'):
        elem_type = field['element_go_type'] or 'types.StringType'
        lines = [
            'if rawSlice_%s := StringSliceFromAPI(%s["%s"]); rawSlice_%s != nil {' % (sn, source_var, jn, sn),
            '\tlv, d := types.ListValueFrom(ctx, %s, rawSlice_%s)' % (elem_type, sn),
            '\tdiags.Append(d...)',
            '\tdata.%s = lv' % pn,
            '} else {',
            '\tdata.%s = types.ListNull(%s)' % (pn, elem_type),
            '}',
        ]
        return lines
    elif t == 'list_nested':
        nested_type = field['nested_type_name']
        sub_fields = field['sub_fields']
        lines = [
            'if rawItems_%s, ok := %s["%s"].([]interface{}); ok && rawItems_%s != nil {' % (sn, source_var, jn, sn),
            '\titems_%s := make([]%s, len(rawItems_%s))' % (sn, nested_type, sn),
            '\tfor i_%s, raw_%s := range rawItems_%s {' % (sn, sn, sn),
            '\t\tm_%s, _ := raw_%s.(map[string]interface{})' % (sn, sn),
            '\t\tif m_%s == nil { m_%s = map[string]interface{}{} }' % (sn, sn),
        ]
        for sf in sub_fields:
            lines.extend(['\t\t' + l for l in go_populate_nested_field(sf, 'm_%s' % sn, 'items_%s[i_%s]' % (sn, sn))])
        lines += [
            '\t}',
            '\tdata.%s = items_%s' % (pn, sn),
            '} else {',
            '\tdata.%s = nil' % pn,
            '}',
        ]
        return lines
    elif t == 'single_nested':
        nested_type = field['nested_type_name']
        sub_fields = field['sub_fields']
        lines = [
            'if rawObj_%s, ok := %s["%s"].(map[string]interface{}); ok {' % (sn, source_var, jn),
            '\tobj_%s := &%s{}' % (sn, nested_type),
        ]
        for sf in sub_fields:
            lines.extend(['\t' + l for l in go_populate_nested_field(sf, 'rawObj_%s' % sn, 'obj_%s' % sn)])
        lines += [
            '\t_ = rawObj_%s' % sn,
            '\tdata.%s = obj_%s' % (pn, sn),
            '} else {',
            '\tdata.%s = nil' % pn,
            '}',
        ]
        return lines
    return []


def go_populate_nested_field(field, source_var, dest_var):
    """Generate assignment for a nested struct field (not using data. prefix)."""
    t = field['tf_attr_type']
    pn = field['pascal_name']
    jn = field['json_name']

    if t == 'string':
        return ['%s.%s = StringFromAPI(%s["%s"])' % (dest_var, pn, source_var, jn)]
    elif t == 'int64':
        return ['%s.%s = Int64FromAPI(%s["%s"])' % (dest_var, pn, source_var, jn)]
    elif t == 'bool':
        return ['%s.%s = BoolFromAPI(%s["%s"])' % (dest_var, pn, source_var, jn)]
    elif t == 'float64':
        return ['%s.%s = Float64FromAPI(%s["%s"])' % (dest_var, pn, source_var, jn)]
    elif t == 'map_string':
        sn = field['snake_name']
        return [
            '// %s: map field — expand manually if needed' % jn,
            '_ = %s["%s"]' % (source_var, jn),
        ]
    else:
        # Deeply nested types (list_nested, single_nested inside another nested):
        # skip for now; field stays at zero value.
        return ['// %s: nested field — expand manually if needed' % jn]


def go_build_body_field(field):
    """Generate Go code to add one field to a request body map."""
    t = field['tf_attr_type']
    sn = field['snake_name']
    pn = field['pascal_name']
    jn = field['json_name']

    if t == 'string':
        return [
            'if !data.%s.IsNull() && !data.%s.IsUnknown() {' % (pn, pn),
            '\tbody["%s"] = data.%s.ValueString()' % (jn, pn),
            '}',
        ]
    elif t == 'int64':
        return [
            'if !data.%s.IsNull() && !data.%s.IsUnknown() {' % (pn, pn),
            '\tbody["%s"] = data.%s.ValueInt64()' % (jn, pn),
            '}',
        ]
    elif t == 'bool':
        return [
            'if !data.%s.IsNull() && !data.%s.IsUnknown() {' % (pn, pn),
            '\tbody["%s"] = data.%s.ValueBool()' % (jn, pn),
            '}',
        ]
    elif t == 'float64':
        return [
            'if !data.%s.IsNull() && !data.%s.IsUnknown() {' % (pn, pn),
            '\tbody["%s"] = data.%s.ValueFloat64()' % (jn, pn),
            '}',
        ]
    elif t == 'map_string':
        return [
            'if !data.%s.IsNull() && !data.%s.IsUnknown() {' % (pn, pn),
            '\tvar m_%s map[string]string' % sn,
            '\tdata.%s.ElementsAs(ctx, &m_%s, false)' % (pn, sn),
            '\tbody["%s"] = m_%s' % (jn, sn),
            '}',
        ]
    elif t in ('list_string', 'list_int64', 'list_bool'):
        return [
            'if !data.%s.IsNull() && !data.%s.IsUnknown() {' % (pn, pn),
            '\tvar sl_%s []string' % sn,
            '\tdata.%s.ElementsAs(ctx, &sl_%s, false)' % (pn, sn),
            '\tbody["%s"] = sl_%s' % (jn, sn),
            '}',
        ]
    elif t == 'list_nested':
        sub_fields = field['sub_fields']
        lines = [
            'if len(data.%s) > 0 {' % pn,
            '\titems_%s := make([]map[string]interface{}, len(data.%s))' % (sn, pn),
            '\tfor i_%s, item_%s := range data.%s {' % (sn, sn, pn),
            '\t\tm_%s := map[string]interface{}{}' % sn,
        ]
        for sf in sub_fields:
            if sf['read_only']:
                continue
            lines.extend(['\t\t' + l for l in go_build_nested_body_field(sf, 'item_%s' % sn, 'm_%s' % sn)])
        lines += [
            '\t\titems_%s[i_%s] = m_%s' % (sn, sn, sn),
            '\t}',
            '\tbody["%s"] = items_%s' % (jn, sn),
            '}',
        ]
        return lines
    elif t == 'single_nested':
        sub_fields = field['sub_fields']
        lines = [
            'if data.%s != nil {' % pn,
            '\tm_%s := map[string]interface{}{}' % sn,
        ]
        for sf in sub_fields:
            if sf['read_only']:
                continue
            lines.extend(['\t' + l for l in go_build_nested_body_field(sf, 'data.%s' % pn, 'm_%s' % sn)])
        lines += [
            '\tbody["%s"] = m_%s' % (jn, sn),
            '}',
        ]
        return lines
    return []


def go_build_nested_body_field(field, source_var, dest_map):
    """Generate body assignment for a nested struct field."""
    t = field['tf_attr_type']
    pn = field['pascal_name']
    jn = field['json_name']

    if t == 'string':
        return ['if !%s.%s.IsNull() { %s["%s"] = %s.%s.ValueString() }' % (
            source_var, pn, dest_map, jn, source_var, pn)]
    elif t == 'int64':
        return ['if !%s.%s.IsNull() { %s["%s"] = %s.%s.ValueInt64() }' % (
            source_var, pn, dest_map, jn, source_var, pn)]
    elif t == 'bool':
        return ['if !%s.%s.IsNull() { %s["%s"] = %s.%s.ValueBool() }' % (
            source_var, pn, dest_map, jn, source_var, pn)]
    elif t == 'float64':
        return ['if !%s.%s.IsNull() { %s["%s"] = %s.%s.ValueFloat64() }' % (
            source_var, pn, dest_map, jn, source_var, pn)]
    else:
        # Complex sub-field (nested object, list, map) — skip; expand manually if needed.
        return ['// %s: complex nested field — expand manually if needed' % jn]


def go_path_params(item_path, resource_info):
    """Generate the map[string]string{...} for path parameter substitution."""
    id_param = resource_info.get('id_param') or 'id'
    params = []
    if item_path:
        for match in _PATH_PARAM_RE.findall(item_path):
            if match == 'org':
                continue
            snake_param = safe_tf_name(camel_to_snake(match))
            if snake_param == safe_tf_name(camel_to_snake(id_param)):
                params.append('"%s": data.Id.ValueString()' % match)
            else:
                params.append('"%s": data.%s.ValueString()' % (match, snake_to_pascal(snake_param)))
    if params:
        return 'map[string]string{%s}' % ', '.join(params)
    return 'map[string]string{}'


# ---------------------------------------------------------------------------
# Resource file generation
# ---------------------------------------------------------------------------

def generate_resource_file(resource_info, spec, overrides):
    resource_name = resource_info['resource_name']
    resource_pascal = snake_to_pascal(resource_name)
    tag = resource_info['tag']
    description = resource_info.get('description', 'Manages %s resources.' % tag)
    description = description.replace('"', '\\"').replace('\n', ' ')

    fields, path_params = merge_resource_fields(resource_info, spec)

    # Apply scope field overrides: add scope fields to path params set
    scope_fields = overrides.get('scope_fields', [])
    for sf in scope_fields:
        path_params.add(sf)

    # Determine which fields go in the create body
    create_field_names = set()
    if resource_info.get('create_schema') and 'properties' in (resource_info.get('create_schema') or {}):
        for pname in resource_info['create_schema']['properties']:
            create_field_names.add(camel_to_snake(pname))

    update_field_names = set()
    if resource_info.get('update_schema') and 'properties' in (resource_info.get('update_schema') or {}):
        for pname in resource_info['update_schema']['properties']:
            update_field_names.add(camel_to_snake(pname))

    collection_path = resource_info.get('collection_path') or ''
    item_path = resource_info.get('item_path') or ''
    id_param = resource_info.get('id_param') or 'id'
    no_create = overrides.get('no_create', False)
    has_update = resource_info.get('has_update', False)
    has_delete = resource_info.get('has_delete', False)
    version_field = overrides.get('version_field')

    # Build schema attributes block
    schema_attrs_lines = ['// id is always computed',
                          '"id": schema.StringAttribute{Computed: true, Description: "The resource ID."},']

    # Add path-param-only fields (scope fields that aren't in any schema)
    field_snake_names = {f['snake_name'] for f in fields}
    for pp in sorted(path_params):
        pp = safe_tf_name(pp)
        if pp not in field_snake_names and pp != 'id':
            pf = {
                'snake_name': pp,
                'pascal_name': snake_to_pascal(pp),
                'json_name': pp,
                'go_type': 'types.String',
                'tf_attr_type': 'string',
                'required': False,
                'read_only': False,
                'description': 'Path parameter: %s.' % pp,
                'enum': None,
                'sub_fields': [],
                'nested_type_name': None,
                'element_go_type': None,
                'in_create': False,
                'in_update': False,
                'in_response': False,
            }
            fields.append(pf)
            # Schema attr is added by the main fields loop below

    for f in fields:
        if f['snake_name'] == 'id':
            continue
        is_pp = f['snake_name'] in path_params
        if f['read_only'] or (not f.get('in_create') and not f.get('in_update') and f.get('in_response')):
            attrs = go_schema_attribute(f, required=False, optional=False, computed=True)
        elif f['required'] and not is_pp:
            attrs = go_schema_attribute(f, required=True, optional=False, computed=False)
        else:
            attrs = go_schema_attribute(f, required=False, optional=True, computed=True)
        schema_attrs_lines.extend(attrs)

    # Build Go struct fields
    struct_fields_lines = ['\tId types.String `tfsdk:"id"`']
    for f in fields:
        if f['snake_name'] == 'id':
            continue
        struct_fields_lines.append(go_struct_field(f))

    # Nested struct definitions
    nested_struct_lines = go_nested_structs(fields)

    # Create body lines
    create_body_lines = []
    for f in fields:
        if f['snake_name'] not in create_field_names or f['read_only']:
            continue
        create_body_lines.extend(go_build_body_field(f))

    # Update body lines
    update_body_lines = []
    if version_field:
        update_body_lines += [
            '// version field for optimistic concurrency',
            'body["%s"] = data.%s.ValueString()' % (version_field, snake_to_pascal(version_field)),
        ]
    for f in fields:
        if f['snake_name'] not in update_field_names or f['read_only']:
            continue
        if f['snake_name'] == version_field:
            continue
        update_body_lines.extend(go_build_body_field(f))

    # Populate model lines
    populate_lines = []
    for f in fields:
        if f['snake_name'] in ('id',):
            continue
        lines = go_populate_model_field(f)
        populate_lines.extend(lines)

    item_path_params = go_path_params(item_path, resource_info)
    collection_path_params = go_path_params(collection_path, resource_info)

    # Format multi-line blocks
    schema_attrs = '\n\t\t\t'.join(schema_attrs_lines)
    struct_fields = '\n'.join(struct_fields_lines)
    nested_structs = '\n'.join(nested_struct_lines)
    create_body = '\n\t'.join(create_body_lines) if create_body_lines else '// no create fields'
    update_body = '\n\t'.join(update_body_lines) if update_body_lines else '// no update fields'
    # Always include _ = diags to suppress "declared and not used" when no map/list field consumes it.
    populate = '\n\t'.join(populate_lines + ['_ = diags']) if populate_lines else '_ = diags'

    # Create method body
    if no_create or not resource_info.get('has_create'):
        create_method = safe_format(
            'func (r *{rp}Resource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {\n'
            '\tresp.Diagnostics.AddError("Create not supported", "This resource does not support creation.")\n'
            '}',
            rp=resource_pascal,
        )
    else:
        create_method = safe_format('''\
func (r *{rp}Resource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {{
\tvar data {rp}ResourceModel
\tresp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
\tif resp.Diagnostics.HasError() {{
\t\treturn
\t}}

\tbody := map[string]interface{}{}
\t{create_body}

\turl := r.client.ResolvePath("{cpath}", {cpparams})
\tresult, err := r.client.Post(ctx, url, body)
\tif err != nil {{
\t\tresp.Diagnostics.AddError("Error creating {tag}", err.Error())
\t\treturn
\t}}

\tdata.Id = StringFromAPI(result["id"])
\tdiags := resp.Diagnostics
\t{populate}
\tresp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}}''',
            rp=resource_pascal, tag=tag, cpath=collection_path,
            cpparams=collection_path_params,
            create_body='\n\t'.join(create_body_lines) if create_body_lines else '// no create fields',
            populate='\n\t'.join(populate_lines + ['_ = diags']) if populate_lines else '_ = diags',
        )

    read_method = safe_format('''\
func (r *{rp}Resource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {{
\tvar data {rp}ResourceModel
\tresp.Diagnostics.Append(req.State.Get(ctx, &data)...)
\tif resp.Diagnostics.HasError() {{
\t\treturn
\t}}

\turl := r.client.ResolvePath("{ipath}", {ipparams})
\tresult, err := r.client.Get(ctx, url)
\tif err != nil {{
\t\tresp.Diagnostics.AddError("Error reading {tag}", err.Error())
\t\treturn
\t}}
\tif result == nil {{
\t\tresp.State.RemoveResource(ctx)
\t\treturn
\t}}

\tdata.Id = StringFromAPI(result["id"])
\tdiags := resp.Diagnostics
\t{populate}
\tresp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}}''',
        rp=resource_pascal, tag=tag, ipath=item_path,
        ipparams=item_path_params,
        populate='\n\t'.join(populate_lines + ['_ = diags']) if populate_lines else '_ = diags',
    )

    if not has_update:
        update_method = safe_format('''\
func (r *{rp}Resource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {{
\tresp.Diagnostics.AddError("Update not supported", "This resource does not support in-place updates.")
}}''', rp=resource_pascal)
    else:
        update_method = safe_format('''\
func (r *{rp}Resource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {{
\tvar data {rp}ResourceModel
\tresp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
\tif resp.Diagnostics.HasError() {{
\t\treturn
\t}}

\tbody := map[string]interface{}{}
\t{update_body}

\turl := r.client.ResolvePath("{ipath}", {ipparams})
\tresult, err := r.client.Patch(ctx, url, body)
\tif err != nil {{
\t\tresp.Diagnostics.AddError("Error updating {tag}", err.Error())
\t\treturn
\t}}

\tdata.Id = StringFromAPI(result["id"])
\tdiags := resp.Diagnostics
\t{populate}
\tresp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}}''',
            rp=resource_pascal, tag=tag, ipath=item_path,
            ipparams=item_path_params,
            update_body='\n\t'.join(update_body_lines) if update_body_lines else '// no update fields',
            populate='\n\t'.join(populate_lines + ['_ = diags']) if populate_lines else '_ = diags',
        )

    if not has_delete:
        delete_method = safe_format('''\
func (r *{rp}Resource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {{
\tresp.Diagnostics.AddError("Delete not supported", "This resource does not support deletion.")
}}''', rp=resource_pascal)
    else:
        delete_body_fields = overrides.get('delete_body_fields', [])
        delete_schema = resource_info.get('delete_schema')
        if delete_schema and 'properties' in delete_schema:
            for pname in delete_schema['properties']:
                sn = camel_to_snake(pname)
                if sn not in delete_body_fields:
                    delete_body_fields.append(sn)

        if delete_body_fields:
            del_body_lines = ['body := map[string]interface{}{}']
            for f in fields:
                if f['snake_name'] in delete_body_fields:
                    del_body_lines.extend(go_build_body_field(f))
            del_body_lines.append('err := r.client.Delete(ctx, url, body)')
        else:
            del_body_lines = ['err := r.client.Delete(ctx, url, nil)']

        delete_method = safe_format('''\
func (r *{rp}Resource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {{
\tvar data {rp}ResourceModel
\tresp.Diagnostics.Append(req.State.Get(ctx, &data)...)
\tif resp.Diagnostics.HasError() {{
\t\treturn
\t}}

\turl := r.client.ResolvePath("{ipath}", {ipparams})
\t{del_body}
\tif err != nil {{
\t\tresp.Diagnostics.AddError("Error deleting {tag}", err.Error())
\t}}
}}''',
            rp=resource_pascal, tag=tag, ipath=item_path,
            ipparams=item_path_params,
            del_body='\n\t'.join(del_body_lines),
        )

    code = safe_format('''\
// Code generated by scripts/generate.py. Do not edit manually.
// SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
// SPDX-License-Identifier: Apache-2.0

package provider

import (
\t"context"
\t"fmt"

\t"github.com/hashicorp/terraform-plugin-framework/diag"
\t"github.com/hashicorp/terraform-plugin-framework/resource"
\t"github.com/hashicorp/terraform-plugin-framework/resource/schema"
\t"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ resource.Resource = &{rp}Resource{}
var _ resource.ResourceWithConfigure = &{rp}Resource{}

func New{rp}Resource() resource.Resource {{
\treturn &{rp}Resource{}
}}

type {rp}Resource struct {{
\tclient *Client
}}

type {rp}ResourceModel struct {{
{struct_fields}
}}

{nested_structs}
func (r *{rp}Resource) Metadata(_ context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {{
\tresp.TypeName = req.ProviderTypeName + "_{rn}"
}}

func (r *{rp}Resource) Schema(_ context.Context, _ resource.SchemaRequest, resp *resource.SchemaResponse) {{
\tresp.Schema = schema.Schema{{
\t\tDescription: "{desc}",
\t\tAttributes: map[string]schema.Attribute{{
\t\t\t{schema_attrs}
\t\t}},
\t}}
}}

func (r *{rp}Resource) Configure(_ context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {{
\tif req.ProviderData == nil {{
\t\treturn
\t}}
\tclient, ok := req.ProviderData.(*Client)
\tif !ok {{
\t\tresp.Diagnostics.AddError(
\t\t\t"Unexpected Resource Configure Type",
\t\t\tfmt.Sprintf("Expected *Client, got: %T.", req.ProviderData),
\t\t)
\t\treturn
\t}}
\tr.client = client
}}

{create_method}

{read_method}

{update_method}

{delete_method}

func (r *{rp}Resource) populateModel(ctx context.Context, data *{rp}ResourceModel, result map[string]interface{}, diags diag.Diagnostics) {{
\t{populate}
}}
''',
        rp=resource_pascal, rn=resource_name, desc=description,
        struct_fields=struct_fields,
        nested_structs=nested_structs + '\n' if nested_struct_lines else '',
        schema_attrs=schema_attrs,
        create_method=create_method,
        read_method=read_method,
        update_method=update_method,
        delete_method=delete_method,
        populate='\n\t'.join(populate_lines + ['_ = diags']) if populate_lines else '_ = diags; _ = ctx; _ = result',
    )

    return code


# ---------------------------------------------------------------------------
# Data source file generation
# ---------------------------------------------------------------------------

def generate_datasource_file(resource_info, spec, overrides):
    resource_name = resource_info['resource_name']
    resource_pascal = snake_to_pascal(resource_name)
    tag = resource_info['tag']
    description = resource_info.get('description', 'Reads %s data.' % tag)
    description = description.replace('"', '\\"').replace('\n', ' ')

    # For data sources, collect only response schema fields
    response_schema = resource_info.get('response_schema') or {}
    ds_fields = analyze_schema_fields(response_schema, spec, resource_pascal + 'Ds')

    collection_path = resource_info.get('collection_path') or ''
    item_path = resource_info.get('item_path') or ''
    has_list = resource_info.get('has_list', False)
    has_get = resource_info.get('has_get', False)

    # Filter params from list endpoint
    filter_fields = []
    for param in resource_info.get('list_query_params', []):
        pname = param.get('name', '')
        sname = safe_tf_name(camel_to_snake(pname))
        filter_fields.append({
            'snake_name': sname,
            'pascal_name': snake_to_pascal(sname),
            'json_name': pname,
            'go_type': 'types.String',
            'tf_attr_type': 'string',
            'required': False,
            'read_only': False,
            'description': param.get('description', 'Filter by %s.' % sname),
            'enum': None,
            'sub_fields': [],
            'nested_type_name': None,
            'element_go_type': None,
        })

    # Add path parameters (e.g., {allocationId}) as Optional filter fields so the user
    # can supply them for single-item lookup. Skip 'org' and 'id' (handled separately).
    existing_filter_names = {ff['snake_name'] for ff in filter_fields}
    for path in (collection_path, item_path):
        for match in _PATH_PARAM_RE.findall(path):
            if match == 'org':
                continue
            sname = safe_tf_name(camel_to_snake(match))
            id_param = resource_info.get('id_param') or 'id'
            if sname == safe_tf_name(camel_to_snake(id_param)) or sname in existing_filter_names:
                continue
            existing_filter_names.add(sname)
            filter_fields.append({
                'snake_name': sname,
                'pascal_name': snake_to_pascal(sname),
                'json_name': match,
                'go_type': 'types.String',
                'tf_attr_type': 'string',
                'required': False,
                'read_only': False,
                'description': 'Path parameter: %s.' % sname,
                'enum': None,
                'sub_fields': [],
                'nested_type_name': None,
                'element_go_type': None,
            })

    # Deduplicate: filter_fields take priority; skip ds_fields with the same snake_name.
    # This prevents duplicate struct fields when a query param also appears in the response schema.
    filter_snake_names = {ff['snake_name'] for ff in filter_fields}
    ds_fields_deduped = [f for f in ds_fields if f['snake_name'] not in filter_snake_names]

    # Schema attributes: filter fields + id for single lookup + response fields
    # Track seen names to prevent duplicates from overlapping schemas.
    seen_attrs = set()
    schema_attrs_lines = []
    if has_get and item_path:
        schema_attrs_lines.append('"id": schema.StringAttribute{Optional: true, Computed: true, Description: "ID of the resource to retrieve. When set, returns a single resource."},')
        seen_attrs.add('id')
    for ff in filter_fields:
        if ff['snake_name'] in seen_attrs:
            continue
        seen_attrs.add(ff['snake_name'])
        schema_attrs_lines.extend(go_schema_attribute(ff, required=False, optional=True, computed=True))
    for f in ds_fields_deduped:
        if f['snake_name'] == 'id':
            if 'id' not in seen_attrs:
                schema_attrs_lines.append('"id": schema.StringAttribute{Computed: true, Description: "The resource ID."},')
                seen_attrs.add('id')
            continue
        if f['snake_name'] in seen_attrs:
            continue
        seen_attrs.add(f['snake_name'])
        schema_attrs_lines.extend(go_schema_attribute(f, required=False, optional=False, computed=True))

    # Struct fields
    seen_fields = set()
    struct_fields_lines = []
    if has_get and item_path:
        struct_fields_lines.append('\tId types.String `tfsdk:"id"`')
        seen_fields.add('id')
    for ff in filter_fields:
        if ff['snake_name'] in seen_fields:
            continue
        seen_fields.add(ff['snake_name'])
        struct_fields_lines.append(go_struct_field(ff))
    for f in ds_fields_deduped:
        if f['snake_name'] == 'id':
            if 'id' not in seen_fields:
                struct_fields_lines.append('\tId types.String `tfsdk:"id"`')
                seen_fields.add('id')
            continue
        if f['snake_name'] in seen_fields:
            continue
        seen_fields.add(f['snake_name'])
        struct_fields_lines.append(go_struct_field(f))

    nested_struct_lines = go_nested_structs(ds_fields_deduped)

    # Populate model
    populate_lines = []
    for f in ds_fields_deduped:
        if f['snake_name'] == 'id':
            continue
        populate_lines.extend(go_populate_model_field(f))

    item_path_params = go_path_params(item_path, resource_info)
    collection_path_params = go_path_params(collection_path, resource_info)

    schema_attrs = '\n\t\t\t'.join(schema_attrs_lines)
    struct_fields = '\n'.join(struct_fields_lines)
    nested_structs = '\n'.join(nested_struct_lines)
    populate = '\n\t'.join(populate_lines + ['_ = diags']) if populate_lines else '_ = diags; _ = ctx; _ = result'

    read_body = []
    if has_get and item_path:
        read_body = safe_format('''\
\tif !data.Id.IsNull() && !data.Id.IsUnknown() && data.Id.ValueString() != "" {{
\t\turl := d.client.ResolvePath("{ipath}", {ipparams})
\t\tresult, err := d.client.Get(ctx, url)
\t\tif err != nil {{
\t\t\tresp.Diagnostics.AddError("Error reading {tag}", err.Error())
\t\t\treturn
\t\t}}
\t\tif result == nil {{
\t\t\tresp.Diagnostics.AddError("{tag} not found", "No resource found with the given id.")
\t\t\treturn
\t\t}}
\t\tdata.Id = StringFromAPI(result["id"])
\t\tdiags := resp.Diagnostics
\t\t{populate}
\t}} else if {has_list} {{
\t\turl := d.client.ResolvePath("{cpath}", {cpparams})
\t\titems, err := d.client.List(ctx, url, map[string]string{})
\t\tif err != nil {{
\t\t\tresp.Diagnostics.AddError("Error listing {tag}", err.Error())
\t\t\treturn
\t\t}}
\t\tif len(items) > 0 {{
\t\t\tresult := items[0]
\t\t\tdata.Id = StringFromAPI(result["id"])
\t\t\tdiags := resp.Diagnostics
\t\t\t{populate}
\t\t}}
\t}}''',
            ipath=item_path, ipparams=item_path_params,
            cpath=collection_path, cpparams=collection_path_params,
            tag=tag, has_list=str(has_list).lower(),
            populate='\n\t\t'.join(populate_lines + ['_ = diags']) if populate_lines else '_ = diags',
        )
    elif has_list:
        read_body = safe_format('''\
\turl := d.client.ResolvePath("{cpath}", {cpparams})
\tqueryParams := map[string]string{}
\t{filter_params}
\titems, err := d.client.List(ctx, url, queryParams)
\tif err != nil {{
\t\tresp.Diagnostics.AddError("Error listing {tag}", err.Error())
\t\treturn
\t}}
\t_ = items
\t// TODO: expose items as a list attribute''',
            cpath=collection_path, cpparams=collection_path_params, tag=tag,
            filter_params='\n\t'.join(
                'queryParams["%s"] = data.%s.ValueString()' % (ff['json_name'], ff['pascal_name'])
                for ff in filter_fields
            ) or '// no filter params',
        )
    else:
        read_body = '\t// singleton resource'

    code = safe_format('''\
// Code generated by scripts/generate.py. Do not edit manually.
// SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
// SPDX-License-Identifier: Apache-2.0

package provider

import (
\t"context"
\t"fmt"

\t"github.com/hashicorp/terraform-plugin-framework/diag"
\t"github.com/hashicorp/terraform-plugin-framework/datasource"
\t"github.com/hashicorp/terraform-plugin-framework/datasource/schema"
\t"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ datasource.DataSource = &{rp}DataSource{}
var _ datasource.DataSourceWithConfigure = &{rp}DataSource{}

func New{rp}DataSource() datasource.DataSource {{
\treturn &{rp}DataSource{}
}}

type {rp}DataSource struct {{
\tclient *Client
}}

type {rp}DataSourceModel struct {{
{struct_fields}
}}

{nested_structs}
func (d *{rp}DataSource) Metadata(_ context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {{
\tresp.TypeName = req.ProviderTypeName + "_{rn}"
}}

func (d *{rp}DataSource) Schema(_ context.Context, _ datasource.SchemaRequest, resp *datasource.SchemaResponse) {{
\tresp.Schema = schema.Schema{{
\t\tDescription: "{desc}",
\t\tAttributes: map[string]schema.Attribute{{
\t\t\t{schema_attrs}
\t\t}},
\t}}
}}

func (d *{rp}DataSource) Configure(_ context.Context, req datasource.ConfigureRequest, resp *datasource.ConfigureResponse) {{
\tif req.ProviderData == nil {{
\t\treturn
\t}}
\tclient, ok := req.ProviderData.(*Client)
\tif !ok {{
\t\tresp.Diagnostics.AddError(
\t\t\t"Unexpected DataSource Configure Type",
\t\t\tfmt.Sprintf("Expected *Client, got: %T.", req.ProviderData),
\t\t)
\t\treturn
\t}}
\td.client = client
}}

func (d *{rp}DataSource) Read(ctx context.Context, req datasource.ReadRequest, resp *datasource.ReadResponse) {{
\tvar data {rp}DataSourceModel
\tresp.Diagnostics.Append(req.Config.Get(ctx, &data)...)
\tif resp.Diagnostics.HasError() {{
\t\treturn
\t}}

{read_body}

\tresp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}}

func (d *{rp}DataSource) populateModel(ctx context.Context, data *{rp}DataSourceModel, result map[string]interface{}, diags diag.Diagnostics) {{
\t{populate}
}}
''',
        rp=resource_pascal, rn=resource_name, desc=description,
        struct_fields=struct_fields,
        nested_structs=nested_structs + '\n' if nested_struct_lines else '',
        schema_attrs=schema_attrs,
        read_body=read_body,
        populate=populate,
    )

    return code


# ---------------------------------------------------------------------------
# Example .tf file generation
# ---------------------------------------------------------------------------

def tf_attribute_value(field):
    """Return a placeholder Terraform value for an example .tf file."""
    t = field['tf_attr_type']
    if t == 'string':
        return '"%s-value"' % field['snake_name'].replace('_', '-')
    elif t == 'int64':
        return '0'
    elif t == 'bool':
        return 'false'
    elif t == 'float64':
        return '0.0'
    elif t == 'map_string':
        return '{\n    key = "value"\n  }'
    elif t in ('list_string', 'list_int64', 'list_bool'):
        return '[]'
    else:
        return '# TODO'


def generate_resource_example(resource_name, resource_info, spec, overrides):
    """Generate an example resource.tf for a resource."""
    fields, path_params = merge_resource_fields(resource_info, spec)
    scope_fields = set(overrides.get('scope_fields', []))

    lines = ['resource "nvidia_infra_controller_%s" "example" {' % resource_name]

    shown = set()

    # Scope fields first (they're path params, so not in create schema, but essential)
    for f in fields:
        if f['snake_name'] in scope_fields and f['snake_name'] not in shown:
            lines.append('  %-30s = "%s-uuid"' % (f['snake_name'], f['snake_name'].replace('_', '-')))
            shown.add(f['snake_name'])

    # Required create-schema fields
    for f in fields:
        if f['snake_name'] in ('id',) or f.get('read_only') or f['snake_name'] in shown:
            continue
        if f['required'] and (f.get('in_create') or f.get('in_update')):
            lines.append('  %-30s = %s' % (f['snake_name'], tf_attribute_value(f)))
            shown.add(f['snake_name'])

    # Common useful optional fields
    for name in ('name', 'description', 'labels'):
        for f in fields:
            if f['snake_name'] == name and name not in shown:
                if f.get('in_create') or f.get('in_update'):
                    lines.append('  %-30s = %s' % (f['snake_name'], tf_attribute_value(f)))
                    shown.add(name)

    lines.append('}')
    return '\n'.join(lines) + '\n'


def generate_datasource_example(resource_name, resource_info):
    """Generate an example data-source.tf for a data source."""
    lines = [
        'data "nvidia_infra_controller_%s" "example" {' % resource_name,
        '  id = "resource-uuid"',
        '}',
        '',
        'output "%s_name" {' % resource_name,
        '  value = data.nvidia_infra_controller_%s.example.name' % resource_name,
        '}',
    ]
    return '\n'.join(lines) + '\n'


def write_example_files(resource_name, resource_info, spec, overrides, output_root, is_read_only):
    """Write example .tf files for a resource and/or data source."""
    if not is_read_only:
        res_dir = os.path.join(output_root, 'examples', 'resources', 'nvidia_infra_controller_%s' % resource_name)
        os.makedirs(res_dir, exist_ok=True)
        example = generate_resource_example(resource_name, resource_info, spec, overrides)
        with open(os.path.join(res_dir, 'resource.tf'), 'w') as f:
            f.write(example)

    ds_dir = os.path.join(output_root, 'examples', 'data-sources', 'nvidia_infra_controller_%s' % resource_name)
    os.makedirs(ds_dir, exist_ok=True)
    example = generate_datasource_example(resource_name, resource_info)
    with open(os.path.join(ds_dir, 'data-source.tf'), 'w') as f:
        f.write(example)


# ---------------------------------------------------------------------------
# Registry file generation
# ---------------------------------------------------------------------------

def generate_registry_file(resource_names, datasource_names):
    resource_constructors = '\n\t\t'.join(
        'New%sResource,' % snake_to_pascal(name) for name in sorted(resource_names)
    )
    datasource_constructors = '\n\t\t'.join(
        'New%sDataSource,' % snake_to_pascal(name) for name in sorted(datasource_names)
    )

    return '''\
// Code generated by scripts/generate.py. Do not edit manually.
// SPDX-FileCopyrightText: Copyright (c) 2026 Fabien Dupont
// SPDX-License-Identifier: Apache-2.0

package provider

import (
\t"github.com/hashicorp/terraform-plugin-framework/datasource"
\t"github.com/hashicorp/terraform-plugin-framework/resource"
)

func providerResources() []func() resource.Resource {
\treturn []func() resource.Resource{
\t\t%s
\t}
}

func providerDataSources() []func() datasource.DataSource {
\treturn []func() datasource.DataSource{
\t\t%s
\t}
}
''' % (resource_constructors, datasource_constructors)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Generate Terraform provider Go files from OpenAPI spec')
    parser.add_argument('--spec', required=True, help='Path to OpenAPI spec.yaml')
    parser.add_argument('--output', required=True, help='Output directory (internal/provider)')
    parser.add_argument('--root', default=None, help='Repo root for example files (default: parent of --output)')
    parser.add_argument('--dry-run', action='store_true', help='Print resource names without writing files')
    args = parser.parse_args()

    repo_root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(args.output)))

    with open(args.spec, 'r') as f:
        spec = yaml.safe_load(f)

    spec_version = spec.get('info', {}).get('version', 'unknown')
    print('Spec version: %s' % spec_version)

    groups = group_paths_by_tag(spec)

    if not args.dry_run:
        os.makedirs(args.output, exist_ok=True)

    resource_names = []
    datasource_names = []
    generated = []

    for tag, group in sorted(groups.items()):
        resource_name = group['resource_name']
        overrides = RESOURCE_OVERRIDES.get(resource_name, {})
        is_read_only = tag in READ_ONLY_TAGS

        resource_info = analyze_resource(tag, group, spec)

        has_readable = resource_info.get('has_list') or resource_info.get('has_get')
        has_writable = resource_info.get('has_create') or resource_info.get('has_update') or resource_info.get('has_delete')

        if is_read_only:
            # Data source only
            if has_readable:
                filename = 'data_source_%s.go' % resource_name
                datasource_names.append(resource_name)
                if args.dry_run:
                    print('  [data-source] %s' % filename)
                else:
                    code = generate_datasource_file(resource_info, spec, overrides)
                    filepath = os.path.join(args.output, filename)
                    with open(filepath, 'w') as fh:
                        fh.write(code)
                    write_example_files(resource_name, resource_info, spec, overrides, repo_root, is_read_only=True)
                    print('  Generated %s + examples' % filepath)
                    generated.append(filename)
        else:
            # Resource (CRUD)
            if has_writable:
                filename = 'resource_%s.go' % resource_name
                resource_names.append(resource_name)
                if args.dry_run:
                    print('  [resource] %s' % filename)
                else:
                    code = generate_resource_file(resource_info, spec, overrides)
                    filepath = os.path.join(args.output, filename)
                    with open(filepath, 'w') as fh:
                        fh.write(code)
                    print('  Generated %s' % filepath)
                    generated.append(filename)

            # Also generate a data source for readable resources
            if has_readable:
                filename = 'data_source_%s.go' % resource_name
                datasource_names.append(resource_name)
                if args.dry_run:
                    print('  [data-source] %s' % filename)
                else:
                    code = generate_datasource_file(resource_info, spec, overrides)
                    filepath = os.path.join(args.output, filename)
                    with open(filepath, 'w') as fh:
                        fh.write(code)
                    print('  Generated %s' % filepath)
                    generated.append(filename)

            # Write example .tf files (resource + data source)
            if not args.dry_run and (has_writable or has_readable):
                write_example_files(resource_name, resource_info, spec, overrides, repo_root, is_read_only=False)

    # Write registry
    if not args.dry_run:
        registry_code = generate_registry_file(resource_names, datasource_names)
        registry_path = os.path.join(args.output, 'resources_registry.go')
        with open(registry_path, 'w') as fh:
            fh.write(registry_code)
        print('  Generated %s' % registry_path)
        generated.append('resources_registry.go')

    print('\nGenerated %d Go files + %d example dirs (%d resources, %d data sources).' % (
        len(generated), len(resource_names) + len(datasource_names),
        len(resource_names), len(datasource_names)))


if __name__ == '__main__':
    main()
