"""
Shared helper utilities extracted from app.py.
"""
import re


def merge_parsed_results(parsed_list: list) -> dict:
    """Merge multiple parsed MuleSoft XML results into a single unified structure."""
    merged = {
        "global_configs": [],
        "flows": [],
        "sub_flows": [],
        "error_handlers": [],
        "global_properties": {},
        "connectors": set(),
        "batch_jobs": [],
        "apikit_configs": [],
        "secure_properties": [],
        "tls_contexts": [],
        "caching_strategies": [],
        "warnings": [],
    }

    seen_flow_names = set()
    seen_sub_flow_names = set()
    seen_config_names = set()

    for parsed in parsed_list:
        for cfg in parsed.get("global_configs", []):
            cfg_name = cfg.get("name", "")
            if cfg_name and cfg_name not in seen_config_names:
                seen_config_names.add(cfg_name)
                merged["global_configs"].append(cfg)
            elif not cfg_name:
                merged["global_configs"].append(cfg)

        for flow in parsed.get("flows", []):
            flow_name = flow.get("name", "")
            if flow_name not in seen_flow_names:
                seen_flow_names.add(flow_name)
                merged["flows"].append(flow)
            else:
                merged["warnings"].append(
                    f"Duplicate flow '{flow_name}' found across XML files — kept first occurrence"
                )

        for sf in parsed.get("sub_flows", []):
            sf_name = sf.get("name", "")
            if sf_name not in seen_sub_flow_names:
                seen_sub_flow_names.add(sf_name)
                merged["sub_flows"].append(sf)
            else:
                merged["warnings"].append(
                    f"Duplicate sub-flow '{sf_name}' found across XML files — kept first occurrence"
                )

        merged["error_handlers"].extend(parsed.get("error_handlers", []))
        merged["global_properties"].update(parsed.get("global_properties", {}))

        connectors = parsed.get("connectors", set())
        if isinstance(connectors, (list, set)):
            merged["connectors"].update(connectors)

        merged["batch_jobs"].extend(parsed.get("batch_jobs", []))
        merged["apikit_configs"].extend(parsed.get("apikit_configs", []))
        merged["secure_properties"].extend(parsed.get("secure_properties", []))
        merged["tls_contexts"].extend(parsed.get("tls_contexts", []))
        merged["caching_strategies"].extend(parsed.get("caching_strategies", []))
        merged["warnings"].extend(parsed.get("warnings", []))

    return merged


def split_comment_separated_xml(content: str) -> list:
    """Split XML content that was concatenated with <!-- File: xxx --> markers."""
    parts = re.split(r'<!--\s*File:\s*(.+?)\s*-->', content)
    results = []
    i = 1
    while i < len(parts):
        name = parts[i].strip()
        xml_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if xml_content:
            results.append((name, xml_content))
        i += 2
    if not results and content.strip():
        results.append(("main.xml", content.strip()))
    return results
