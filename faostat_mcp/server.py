"""
FAOSTAT MCP Server

Exposes the full FAOSTAT REST API as MCP tools, usable by Claude Desktop,
Claude Code, Cursor, and any other MCP-compatible AI client.

Run in development mode:
  mcp dev faostat_mcp/server.py

Run as a module (for Claude Desktop config):
  python -m faostat_mcp.server
"""

import csv
import io
import json
import os
import logging
from typing import Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from .client import (
    faostat_get,
    faostat_post,
    DEFAULT_LANG,
    _get_token_manager,
    _get_redis_connector,
    HybridCaching,
    FAOSTATAuthError,
    FAOSTATRateLimitError,
    FAOSTATServerError,
)

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# ---------------------------------------------------------------------------
# Response formatting helpers
# ---------------------------------------------------------------------------

def _format_rows(
    rows: list[dict[str, Any]],
    response_format: str = "objects",
    fields: list[str] | None = None,
) -> str:
    """Convert a list of row-dicts to the requested output format.

    Args:
        rows: List of dicts (each dict is one data row).
        response_format: "objects" | "compact" | "csv"
        fields: If provided, only include these column names.

    Returns:
        A string: JSON for objects/compact, plain CSV text for csv.
    """
    if not rows:
        return json.dumps([])

    # Field filtering
    if fields:
        valid = [f for f in fields if f in rows[0]]
        if valid:
            rows = [{k: row.get(k) for k in valid} for row in rows]

    if response_format == "objects":
        return json.dumps(rows)

    # Derive column names from the first row
    columns = list(rows[0].keys())

    if response_format == "csv":
        buf = io.StringIO(newline="")
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])
        return buf.getvalue()

    # "compact" — columnar format
    return json.dumps({
        "columns": columns,
        "rows": [[row.get(c) for c in columns] for row in rows],
    })

# Initialise the FastMCP server
mcp = FastMCP(
    name="faostat",
    instructions=(
        "You have access to the FAOSTAT database — the UN Food and Agriculture Organization's "
        "statistical database covering agriculture, food security, trade, emissions, and more "
        "for ~245 countries. Use these tools to answer questions about global food and agriculture "
        "data. Always start by exploring available groups and domains if you are unsure which "
        "domain contains the data you need."
    ),
)

# Initialise the HybridCaching Manager
try:
    caching_manager = HybridCaching(
        mem_cache_ttl=int(os.getenv("MEM_CACHE_TTL", "1200")),
        redis_cache_ttl=int(os.getenv("REDIS_CACHE_TTL", "1800")),
        max_mem_cache_size=int(os.getenv("MAX_MEM_CACHE_SIZE", "256")),
        user_token=str(os.getenv("FAOSTAT_API_TOKEN", "")),
        redis_conn=_get_redis_connector(),
    )
except ValueError:
    caching_manager = HybridCaching()

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_ping() -> str:
    """
    Check the FAOSTAT API health status.
    Returns a status message indicating if the API is online.
    """
    try:
        result = await faostat_get("/ping")
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_refresh_token() -> str:
    """
    Force-refresh the FAOSTAT API authentication token.

    Use this tool when other FAOSTAT tools fail with 401 Unauthorized or
    token-expiry errors. It logs in with the configured credentials
    (FAOSTAT_USERNAME + FAOSTAT_PASSWORD) and obtains a fresh JWT token.

    Requires FAOSTAT_USERNAME and FAOSTAT_PASSWORD to be set in the .env file.
    """
    tm = _get_token_manager()
    try:
        await tm.force_refresh()
        return json.dumps({"status": "ok", "message": "Token refreshed successfully."})
    except FAOSTATAuthError as exc:
        return json.dumps({"status": "error", "message": str(exc)})


# ---------------------------------------------------------------------------
# Discovery: groups, domains, structure
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_list_groups(lang: str = DEFAULT_LANG) -> str:
    """
    List all top-level FAOSTAT data groups (e.g. Production, Trade, Food Security).
    Use this to discover what categories of data are available.

    Args:
        lang: Language code (default: 'en')
    """
    try:
        # Check memory Cache
        arg_dict = {'lang':lang}
        cached_val = caching_manager.get_data("faostat_list_groups", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/groups/")
        # Save to memory Cache
        caching_manager.set_data("faostat_list_groups", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_groups_and_domains(lang: str = DEFAULT_LANG) -> str:
    """
    Get the full hierarchical tree of all FAOSTAT groups and their domains.
    Use this for a complete overview of all available datasets.

    Args:
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {'lang':lang}
        cached_val = caching_manager.get_data("faostat_groups_and_domains", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/groupsanddomains")
        caching_manager.set_data("faostat_groups_and_domains", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_list_domains(group_code: str, lang: str = DEFAULT_LANG) -> str:
    """
    List all datasets (domains) within a FAOSTAT group.

    Args:
        group_code: The group code (e.g. 'Q' for Production, 'T' for Trade,
                    'FS' for Food Security). Get codes from faostat_list_groups.
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {'group_code':group_code,'lang':lang}
        cached_val = caching_manager.get_data("faostat_list_domains", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/domains/{group_code}/")
        caching_manager.set_data("faostat_list_domains", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_get_dimensions(domain_code: str, lang: str = DEFAULT_LANG) -> str:
    """
    Get the structure of a domain — what dimensions (filters) are available,
    such as area (country), item (commodity), element (measure), and year.

    Args:
        domain_code: Domain code (e.g. 'QCL' for Crops and Livestock,
                     'TM' for Trade, 'FS' for Food Security)
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {'domain_code': domain_code, 'lang': lang}
        cached_val = caching_manager.get_data("faostat_get_dimensions", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/dimensions/{domain_code}/")
        caching_manager.set_data("faostat_get_dimensions", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Codes (lookup tables for filter values)
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_get_codes(
    dimension_id: str,
    domain_code: str,
    lang: str = DEFAULT_LANG,
    limit: int = 0,
) -> str:
    """
    Get the list of available FILTER codes for a specific dimension in a domain.
    You MUST call this before faostat_get_data to get the correct codes for filtering.

    IMPORTANT: For the 'element' dimension, filter codes differ from the display
    codes shown in data responses. For example in QCL, faostat_get_codes returns
    filter code '2510' for Production, but the data response shows '5510' in the
    Element Code column. Always use the codes from this tool when filtering.

    Args:
        dimension_id: Dimension identifier (e.g. 'area', 'item', 'element', 'year')
        domain_code: Domain code (e.g. 'QCL', 'TM', 'FS')
        lang: Language code (default: 'en')
        limit: Maximum number of codes to return (default: 0 = no limit).
               Useful for large dimensions like 'item' which can have 1000+ entries.

    Examples:
        faostat_get_codes(dimension_id='element', domain_code='QCL')
        → Returns element filter codes: 2510=Production, 2312=Area harvested, etc.

        faostat_get_codes(dimension_id='area', domain_code='QCL')
        → Returns country/area codes: 2=Afghanistan, 3=Albania, etc.
    """
    try:
        arg_dict = {
            'dimension_id': dimension_id,
            'domain_code': domain_code,
            'lang': lang,
            'limit': limit,
            }
        cached_val = caching_manager.get_data("faostat_get_codes", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/codes/{dimension_id}/{domain_code}")
        codes_list = result.get("data", result) if isinstance(result, dict) else result
        if limit > 0 and isinstance(codes_list, list) and len(codes_list) > limit:
            truncated = {
                "data": codes_list[:limit],
                "_truncated": True,
                "_total_codes": len(codes_list),
                "_returned_codes": limit,
            }
            caching_manager.set_data("faostat_get_codes", arg_dict, truncated)
            return json.dumps(truncated)
        caching_manager.set_data("faostat_get_codes", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Data retrieval
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_get_data(
    domain_code: str,
    lang: str = DEFAULT_LANG,
    area: str | None = None,
    element: str | None = None,
    item: str | None = None,
    year: str | None = None,
    area_cs: str | None = None,
    element_cs: str | None = None,
    item_cs: str | None = None,
    year_cs: str | None = None,
    show_codes: bool = False,
    show_unit: bool = True,
    show_flags: bool = False,
    null_values: bool = False,
    limit: int = 50,
    response_format: str = "objects",
    fields: str | None = None,
) -> str:
    """
    Fetch statistical data from a FAOSTAT domain.
    This is the primary tool for retrieving actual data values.

    IMPORTANT: For large domains, always filter by area/item/year to avoid
    very large responses. Check query size first with faostat_get_datasize.

    IMPORTANT: Element codes used for filtering differ from the display codes
    returned in the response. Always use faostat_get_codes(dimension_id='element',
    domain_code=...) to get the correct filter codes. For example, in QCL:
      - Filter with element='2510' → response shows Element Code '5510' (Production)
      - Filter with element='2312' → response shows Element Code '5312' (Area harvested)

    Args:
        domain_code: Domain code (e.g. 'QCL' for Crops and Livestock Products)
        lang: Language code (default: 'en')
        area: Country/area codes, comma-separated (e.g. '2' for Afghanistan).
              Use faostat_get_codes(dimension_id='area', domain_code=...) to find codes.
        element: Element FILTER codes, comma-separated (e.g. '2510' for Production,
                 '2312' for Area harvested in QCL). These differ from the display codes
                 in the response. Always look up via faostat_get_codes first.
        item: Item/commodity codes, comma-separated (e.g. '515' for Apples, '15' for Wheat)
        year: Year codes, comma-separated (e.g. '2020' or '2018,2019,2020')
        area_cs: Area code set name (alternative to individual area codes)
        element_cs: Element code set name
        item_cs: Item code set name
        year_cs: Year code set name (e.g. 'FAO_YEAR_RECENT' for recent years)
        show_codes: Include code columns in response (default: False — names are
                    more useful for interpretation; codes are for filtering)
        show_unit: Include unit column in response (default: True)
        show_flags: Include data quality flags (default: False — rarely needed)
        null_values: Include rows with null values (default: False)
        limit: Maximum number of rows to return (default: 50). Set to 0 for no limit.
               Use faostat_get_datasize first if you expect a large result set.
        response_format: Output format (default: 'objects').
            - 'objects': Array of self-describing JSON objects (best LLM comprehension)
            - 'compact': Columnar {"columns": [...], "rows": [[...]]} (~3x smaller)
            - 'csv': Plain CSV text with header row (~4x smaller)
            Use 'compact' or 'csv' when retrieving larger datasets to reduce token usage.
        fields: Comma-separated column names to include (e.g. 'Area,Year,Value').
                Omit to include all columns. Use to reduce response size further.

    Examples:
        # Apple production in Afghanistan 2024 (element 2510 = Production filter code)
        faostat_get_data('QCL', area='2', item='515', element='2510', year='2024')

        # Food security indicators for all African countries
        faostat_get_data('FS', area_cs='AFRICA')

        # Minimal response — only area, year and value in CSV format
        faostat_get_data('QCL', area='231', item='15', element='2510', year='2024',
                         response_format='csv', fields='Area,Year,Value')
    """
    try:
        # Validate response_format
        if response_format not in ("objects", "compact", "csv"):
            return json.dumps({
                "error": "ValueError",
                "message": f"Invalid response_format '{response_format}'. Use 'objects', 'compact', or 'csv'.",
            })

        arg_dict = {
            'domain_code': domain_code,
            'lang': lang,
            'area': area,
            'element': element,
            'item': item,
            'year': year,
            'area_cs': area_cs,
            'element_cs': element_cs,
            'item_cs': item_cs,
            'year_cs': year_cs,
            'show_codes': show_codes,
            'show_unit': show_unit,
            'show_flags': show_flags,
            'null_values': null_values,
            'limit': limit,
        }
        cached_val = caching_manager.get_data("faostat_get_data", arg_dict)
        if cached_val:
            return json.dumps(cached_val)

        params: dict[str, Any] = {
            "show_codes": show_codes,
            "show_unit": show_unit,
            "show_flags": show_flags,
            "null_values": null_values,
            "output_type": "objects",
        }
        for key, val in [
            ("area", area), ("element", element), ("item", item), ("year", year),
            ("area_cs", area_cs), ("element_cs", element_cs),
            ("item_cs", item_cs), ("year_cs", year_cs),
        ]:
            if val is not None:
                params[key] = val

        result = await faostat_get(f"/{lang}/data/{domain_code}/", params=params)
        arg_dict.update({'total':len(result)})

        # Extract data rows and optional envelope
        truncated_meta: dict[str, Any] | None = None

        if isinstance(result, list):
            data_rows = result
        elif isinstance(result, dict) and isinstance(result.get("data"), list):
            data_rows = result["data"]
        else:
            # Not tabular data — return as-is
            return json.dumps(result)

        # Apply row limit to prevent context window overflow
        if limit > 0:
            total = len(data_rows)
            if total > limit:
                data_rows = data_rows[:limit]
                truncated_meta = {
                    "_truncated": True,
                    "_total_rows": total,
                    "_returned_rows": limit,
                    "_hint": "Results truncated. Use faostat_get_datasize to check size, then filter further or increase limit.",
                }

        # Parse fields parameter
        parsed_fields = [f.strip() for f in fields.split(",")] if fields else None

        # Format the data rows
        formatted = _format_rows(data_rows, response_format=response_format, fields=parsed_fields)

        # CSV returns plain text
        if response_format == "csv":
            if truncated_meta:
                meta = f"# truncated: {truncated_meta['_total_rows']} total rows, {truncated_meta['_returned_rows']} returned\n"
                result = meta + formatted
            else:
                result = formatted
            caching_manager.set_data("faostat_get_data", arg_dict, result)
            return result

        # For objects/compact, attach truncation metadata if needed
        parsed = json.loads(formatted)
        if truncated_meta:
            if response_format == "compact":
                result = json.dumps({**parsed, **truncated_meta})
            else:
                result = json.dumps({"data": parsed, **truncated_meta})
        else:
            result = formatted

        caching_manager.set_data("faostat_get_data", arg_dict, json.loads(result) if isinstance(result, str) else result)
        return result
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_get_datasize(
    domain_code: str,
    lang: str = DEFAULT_LANG,
    area: str | None = None,
    element: str | None = None,
    item: str | None = None,
    year: str | None = None,
    area_cs: str | None = None,
    element_cs: str | None = None,
    item_cs: str | None = None,
    year_cs: str | None = None,
) -> str:
    """
    Estimate the number of rows a data query will return BEFORE fetching.
    Use this to check if a query is too large before calling faostat_get_data.
    Accepts the same filter parameters as faostat_get_data.

    Args:
        domain_code: Domain code (e.g. 'QCL', 'TM', 'FS')
        lang: Language code (default: 'en')
        area: Country/area codes, comma-separated
        element: Element filter codes, comma-separated
        item: Item/commodity codes, comma-separated
        year: Year codes, comma-separated
        area_cs: Area code set name
        element_cs: Element code set name
        item_cs: Item code set name
        year_cs: Year code set name
    """
    try:
        arg_dict = {
            'domain_code': domain_code, 
            'lang': lang,
            'area': area,
            'element': element,
            'item': item,
            'year': year,
            'area_cs': area_cs,
            'element_cs': element_cs,
            'item_cs': item_cs,
            'year_cs': year_cs,
            }

        cached_val = caching_manager.get_data("faostat_get_datasize", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        payload: dict[str, Any] = {"domain_code": domain_code}
        for key, val in [
            ("area", area), ("element", element), ("item", item), ("year", year),
            ("area_cs", area_cs), ("element_cs", element_cs),
            ("item_cs", item_cs), ("year_cs", year_cs),
        ]:
            if val is not None:
                payload[key] = val
        result = await faostat_post(f"/{lang}/datasize/", json=payload)
        caching_manager.set_data("faostat_get_datasize", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Definitions & Metadata
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_get_definitions(domain_code: str, lang: str = DEFAULT_LANG) -> str:
    """
    Get all definitions (descriptions of items, elements, flags) for a domain.

    Args:
        domain_code: Domain code (e.g. 'QCL', 'FS', 'TM')
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {
            'domain_code': domain_code, 
            'lang': lang,
            }
        cached_val = caching_manager.get_data("faostat_get_definitions", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/definitions/domain/{domain_code}")
        caching_manager.set_data("faostat_get_definitions", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_get_definitions_by_type(
    domain_code: str,
    definition_type: str,
    lang: str = DEFAULT_LANG,
) -> str:
    """
    Get definitions for a domain filtered by type (e.g. items, elements, flags).

    Args:
        domain_code: Domain code (e.g. 'QCL')
        definition_type: Type of definition. Use faostat_definition_types to see options.
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {
            'domain_code': domain_code, 
            'definition_type': definition_type, 
            'lang': lang,
            }
        cached_val = caching_manager.get_data("faostat_get_definitions_by_type", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/definitions/domain/{domain_code}/{definition_type}")
        caching_manager.set_data("faostat_get_definitions_by_type", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_definition_types(lang: str = DEFAULT_LANG) -> str:
    """
    List all available definition types (used with faostat_get_definitions_by_type).

    Args:
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {'lang': lang}
        cached_val = caching_manager.get_data("faostat_definition_types", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/definitions/types")
        caching_manager.set_data("faostat_definition_types", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_get_metadata(domain_code: str, lang: str = DEFAULT_LANG) -> str:
    """
    Get full methodology and metadata for a domain — including data sources,
    collection methods, coverage, and limitations.

    Args:
        domain_code: Domain code (e.g. 'QCL', 'FS', 'GCE')
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {
            'domain_code': domain_code,
            'lang': lang,
            }
        cached_val = caching_manager.get_data("faostat_get_metadata", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/metadata/{domain_code}")
        caching_manager.set_data("faostat_get_metadata", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_get_metadata_print(domain_code: str, lang: str = DEFAULT_LANG) -> str:
    """
    Get metadata for a domain in a printable/simplified format.

    Args:
        domain_code: Domain code (e.g. 'QCL', 'FS')
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {
            'domain_code': domain_code,
            'lang': lang,
            }
        cached_val = caching_manager.get_data("faostat_get_metadata_print", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/metadata_print/{domain_code}")
        caching_manager.set_data("faostat_get_metadata_print", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Bulk downloads & Documents
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_list_bulk_downloads(domain_code: str, lang: str = DEFAULT_LANG) -> str:
    """
    List available bulk download files for a domain (ZIP/CSV archives).
    These contain the full domain dataset and can be very large.

    Args:
        domain_code: Domain code (e.g. 'QCL', 'TM')
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {
            'domain_code': domain_code,
            'lang': lang,
            }
        cached_val = caching_manager.get_data("faostat_list_bulk_downloads", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/bulkdownloads/{domain_code}/")
        caching_manager.set_data("faostat_list_bulk_downloads", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_list_documents(domain_code: str, lang: str = DEFAULT_LANG) -> str:
    """
    List related documents (methodology papers, questionnaires) for a domain.

    Args:
        domain_code: Domain code (e.g. 'QCL', 'FS')
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {
            'domain_code': domain_code,
            'lang': lang,
            }
        cached_val = caching_manager.get_data("faostat_list_documents", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_get(f"/{lang}/documents/{domain_code}/")
        caching_manager.set_data("faostat_list_documents", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_get_rankings(
    domain_code: str,
    element_code: str,
    item_code: str,
    year: str,
    lang: str = DEFAULT_LANG,
    limit: int = 10,
    response_format: str = "objects",
) -> str:
    """
    Get rankings — e.g. top countries by production, yield, or trade value.
    Use this to answer "which country produces the most X?" questions.

    NOTE: element_code here is the DISPLAY code (e.g. '5510'), not the filter code
    used in faostat_get_data. Rankings use the same codes shown in data responses.

    Args:
        domain_code: Domain to rank within (e.g. 'QCL')
        element_code: Display element code to rank by (e.g. '5510' for Production in QCL)
        item_code: Commodity code (e.g. '56' for Maize, '15' for Wheat)
        year: The year to rank for (e.g. '2022')
        lang: Language code (default: 'en')
        limit: Number of top results to return (default: 10)
        response_format: Output format: 'objects' (default), 'compact', or 'csv'

    Example:
        faostat_get_rankings(domain_code='QCL', element_code='5510',
                             item_code='56', year='2022', limit=10)
        → Top 10 maize-producing countries in 2022
    """
    try:
        if response_format not in ("objects", "compact", "csv"):
            return json.dumps({
                "error": "ValueError",
                "message": f"Invalid response_format '{response_format}'. Use 'objects', 'compact', or 'csv'.",
            })

        arg_dict = {
            'domain_code': domain_code,
            'element_code': element_code,
            'item_code': item_code,
            'year': year,
            'lang': lang,
            'limit': limit,
        }
        cached_val = caching_manager.get_data("faostat_get_rankings", arg_dict)
        if cached_val:
            return json.dumps(cached_val)

        payload: dict[str, Any] = {
            "domain_code": domain_code,
            "element_code": element_code,
            "item_code": item_code,
            "year": year,
            "limit": limit,
        }
        result = await faostat_post(f"/{lang}/rankings/", json=payload)
        caching_manager.set_data("faostat_get_rankings", arg_dict, result)

        if isinstance(result, list) and result:
            return _format_rows(result, response_format=response_format)

        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@mcp.tool()
async def faostat_get_report_data(payload: dict[str, Any], lang: str = DEFAULT_LANG) -> str:
    """
    Get structured report data from FAOSTAT.

    Args:
        payload: Report query parameters (structure depends on report type)
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {'lang': lang}
        arg_dict.update(payload)
        cached_val = caching_manager.get_data("faostat_get_report_data", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_post(f"/{lang}/report/data/", json=payload)
        caching_manager.set_data("faostat_get_report_data", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


@mcp.tool()
async def faostat_get_report_headers(payload: dict[str, Any], lang: str = DEFAULT_LANG) -> str:
    """
    Get the column headers/schema for a report before fetching its data.

    Args:
        payload: Report query parameters
        lang: Language code (default: 'en')
    """
    try:
        arg_dict = {'lang': lang}
        arg_dict.update(payload)
        cached_val = caching_manager.get_data("faostat_get_report_headers", arg_dict)
        if cached_val:
            return json.dumps(cached_val)
        result = await faostat_post(f"/{lang}/report/headers/", json=payload)
        caching_manager.set_data("faostat_get_report_headers", arg_dict, result)
        return json.dumps(result)
    except (FAOSTATAuthError, FAOSTATRateLimitError, FAOSTATServerError) as exc:
        return json.dumps({"error": type(exc).__name__, "message": str(exc)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the MCP server (stdio transport for Claude Desktop/Code)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
