import json
import os
from collections import defaultdict
from typing import Dict, List, Set

from utils import (
    VPNConfig,
    COUNTRY_NAME_MAP,
    add_repo_to_uri_fragment,
    add_repo_to_vmess,
    country_from_flag,
    country_from_name_heuristic,
    decode_maybe_base64,
    detect_protocol,
    ensure_dirs,
    extract_flag_from_name,
    extract_host_port_from_uri,
    fetch_url,
    geoip_lookup,
    get_flag_for_iso,
    logger,
    normalize_name,
    parse_subscription_text,
    resolve_host_to_ip,
    write_json_file,
    write_text_file,
    root_path,
)

URLS_FILE = root_path("urls.txt")
TGK_FILE = root_path("configs/tgk/tgk_raw.txt")


def load_urls() -> List[str]:
    urls: List[str] = []
    if not URLS_FILE.exists():
        logger.error(f"{URLS_FILE} not found")
        return urls

    with open(URLS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)

    return urls


def process_line(line: str, geo_cache: Dict[str, tuple], seen_keys: Set[str]) -> VPNConfig | None:
    protocol = detect_protocol(line)
    if not protocol:
        return None

    host, port = extract_host_port_from_uri(line, protocol)
    if not host or not port:
        return None

    key = f"{protocol}:{host}:{port}"
    if key in seen_keys:
        return None
    seen_keys.add(key)

    # --- Определяем флаг, страну, ISO ---
    flag = extract_flag_from_name(line) or ""

    if flag:
        iso, country_name = country_from_flag(flag)
    else:
        ip = resolve_host_to_ip(host)
        if ip:
            iso, country_name = geoip_lookup(ip, geo_cache)
        else:
            iso, country_name = country_from_name_heuristic(line)
        flag = get_flag_for_iso(iso)

    # --- Если страна не определена — отправляем в unknown ---
    if not iso:
        iso = "unknown"
        country_name = "Unknown"
        flag = "🏳️"

    # --- Имя для отображения ---
    display_name = normalize_name(flag)

    # --- Нормализация ссылки ---
    if protocol == "vmess":
        normalized_raw = add_repo_to_vmess(line, display_name)
    else:
        normalized_raw = add_repo_to_uri_fragment(line, display_name)

    return VPNConfig(
        protocol=protocol,
        raw=normalized_raw,
        country_iso=iso,
        country_name=country_name,
        flag=flag,
        host=host,
        port=port,
        name=display_name,
    )


def load_telethon_configs(geo_cache, seen_keys) -> List[VPNConfig]:
    configs = []

    if not TGK_FILE.exists():
        return configs

    logger.info("Loading Telethon configs...")

    with open(TGK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cfg = process_line(line, geo_cache, seen_keys)
            if cfg:
                cfg.source = "TGK"
                configs.append(cfg)

    return configs


def main() -> None:
    logger.info("Starting parser...")
    ensure_dirs()

    geo_cache: Dict[str, tuple] = {}
    seen_keys: Set[str] = set()
    configs: List[VPNConfig] = []

    # --- 1. Load Telethon configs ---
    configs.extend(load_telethon_configs(geo_cache, seen_keys))

    # --- 2. Load URL configs ---
    urls = load_urls()
    for url in urls:
        data = fetch_url(url)
        if data is None:
            continue

        text = decode_maybe_base64(data)
        lines = parse_subscription_text(text)

        for line in lines:
            cfg = process_line(line, geo_cache, seen_keys)
            if cfg:
                configs.append(cfg)

    # --- 3. Group by country and protocol ---
    by_country: Dict[str, List[VPNConfig]] = defaultdict(list)
    by_protocol: Dict[str, List[VPNConfig]] = defaultdict(list)

    for cfg in configs:
        by_country[cfg.country_iso].append(cfg)
        by_protocol[cfg.protocol].append(cfg)

    # --- 4. Write all configs ---
    write_text_file(
        "configs/all.txt",
        [c.raw for c in configs],
        scope="ALL",
        alive_count=None
    )

    # --- 5. Write by country ---
    for iso, items in by_country.items():
        filename = f"{COUNTRY_NAME_MAP.get(iso, 'unknown')}.txt"
        path = f"configs/countries/{filename}"

        write_text_file(
            path,
            [c.raw for c in items],
            scope=f"COUNTRY {iso}",
            alive_count=None
        )

    # --- 6. Write by protocol ---
    for proto, items in by_protocol.items():
        path = f"configs/protocols/{proto}.txt"

        write_text_file(
            path,
            [c.raw for c in items],
            scope=f"PROTO {proto.upper()}",
            alive_count=None
        )

    # --- 7. Write JSON ---
    write_json_file("configs/configs.json", [c.__dict__ for c in configs])

    stats = {
        "total": len(configs),
        "by_country": {iso: len(items) for iso, items in by_country.items()},
        "by_protocol": {proto: len(items) for proto, items in by_protocol.items()},
    }

    write_json_file("configs/stats.json", stats)

    logger.info("Parser finished")


if __name__ == "__main__":
    main()
