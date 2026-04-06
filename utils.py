import base64
import json
import logging
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib import request, parse

# ---------- ПУТИ ----------
ROOT = Path(__file__).resolve().parent  # корень репозитория

def root_path(*parts):
    return ROOT.joinpath(*parts)

# ---------- ЛОГИ ----------
def setup_logger(name: str = "ghost_vpn") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger

logger = setup_logger()

# ---------- КОНСТАНТЫ ----------
DEFAULT_NAME = "Gh0st_WhiteList" # Изменил под твой запрос

COUNTRY_NAME_MAP = {
    "RU": "russia", "US": "usa", "DE": "germany", "FR": "france",
    "NL": "netherlands", "GB": "united-kingdom", "UK": "united-kingdom",
    "TR": "turkey", "SG": "singapore", "JP": "japan", "KR": "south-korea",
    "CN": "china", "HK": "hong-kong", "TW": "taiwan", "CA": "canada",
    "BR": "brazil", "IN": "india", "ES": "spain", "IT": "italy",
    "SE": "sweden", "CH": "switzerland", "PL": "poland", "UA": "ukraine",
}

FLAG_TO_ISO = {
    "🇷🇺": "RU", "🇺🇸": "US", "🇩🇪": "DE", "🇫🇷": "FR", "🇳🇱": "NL",
    "🇬🇧": "GB", "🇹🇷": "TR", "🇸🇬": "SG", "🇯🇵": "JP", "🇰🇷": "KR",
    "🇨🇳": "CN", "🇭🇰": "HK", "🇹🇼": "TW", "🇨🇦": "CA", "🇧🇷": "BR",
    "🇮🇳": "IN", "🇪🇸": "ES", "🇮🇹": "IT", "🇸🇪": "SE", "🇨🇭": "CH",
    "🇵🇱": "PL", "🇺🇦": "UA"
}

ISO_TO_FLAG = {v: k for k, v in FLAG_TO_ISO.items()}

# ---------- МОДЕЛЬ ----------
@dataclass
class VPNConfig:
    protocol: str
    raw: str
    country_iso: str
    country_name: str
    flag: str
    host: str
    port: int
    name: str
    source: str = "URL"
    latency_ms: Optional[float] = None

# ---------- FS ----------
def ensure_dirs() -> None:
    dirs = [
        "configs",
        "configs/countries",
        "configs/protocols",
        "configs/api",
        "configs/api/by_country",
        "configs/api/by_protocol",
        "configs/tgk",
        "configs/tgk/countries",
        "history",
        "charts",
    ]
    for d in dirs:
        os.makedirs(root_path(d), exist_ok=True)

# ---------- ЗАПИСЬ TXT ----------
def write_text_file(path: str, lines: List[str], scope: str | None = None, alive_count: int | None = None) -> None:
    full_path = root_path(path)
    os.makedirs(full_path.parent, exist_ok=True)

    if scope is None:
        scope = "ALL"
    else:
        # Эта строка удаляет "COUNTRY " из текста, если оно там есть
        scope = scope.replace("COUNTRY ", "")

    count = alive_count if alive_count is not None else len(lines)

    header = [
        f"# profile-title: Gh0st_WhiteList [{scope}]",
        "# profile-web-page: https://github.com",
        "# support-url: https://t.me",
        "# profile-update-interval: 1",
        "# subscription-userinfo: upload=0; download=0; total=854347202560000; expire=0",
        f"# Всего рабочих: {count}",
        "",
    ]

    with open(full_path, "w", encoding="utf-8") as f:
        for h in header:
            f.write(h + "\n")
        for line in lines:
            f.write(line.strip() + "\n")

def write_json_file(path: str, data) -> None:
    full_path = root_path(path)
    os.makedirs(full_path.parent, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- HTTP ----------
def fetch_url(url: str, timeout: int = 15) -> Optional[bytes]:
    logger.info(f"Fetching URL: {url}")
    try:
        req = request.Request(url, headers={"User-Agent": "GhostWhiteListVPN/1.0"})
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None

# ---------- Base64 ----------
def is_base64_data(data: bytes) -> bool:
    text = data.strip()
    if b"\n" in text or b" " in text:
        return False
    try:
        base64.b64decode(text + b"==", validate=True)
        return True
    except Exception:
        return False

def decode_maybe_base64(data: bytes) -> str:
    if is_base64_data(data):
        try:
            decoded = base64.b64decode(data + b"==")
            return decoded.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("utf-8", errors="ignore")
    return data.decode("utf-8", errors="ignore")

# ---------- ПАРСИНГ ----------
def parse_subscription_text(text: str) -> List[str]:
    lines = []
    for line in text.replace("\r", "").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines

def detect_protocol(line: str) -> Optional[str]:
    lower = line.lower()
    if lower.startswith("vmess://"): return "vmess"
    if lower.startswith("vless://"): return "vless"
    if lower.startswith("trojan://"): return "trojan"
    if lower.startswith("ss://"): return "ss"
    return None

# ---------- URI ----------
def extract_host_port_from_uri(uri: str, protocol: str) -> Tuple[str, int]:
    if protocol == "vmess":
        try:
            payload = uri[len("vmess://"):]
            data = base64.b64decode(payload + "==")
            obj = json.loads(data.decode("utf-8"))
            return obj.get("add", ""), int(obj.get("port", 0))
        except:
            return "", 0

    try:
        parsed = parse.urlparse(uri)
        return parsed.hostname or "", parsed.port or 0
    except:
        return "", 0

# ---------- СТРАНА ----------
def extract_flag_from_name(name: str) -> Optional[str]:
    for flag in FLAG_TO_ISO:
        if flag in name:
            return flag
    return None

def country_from_flag(flag: str) -> Tuple[str, str]:
    iso = FLAG_TO_ISO.get(flag, "UN")
    return iso, COUNTRY_NAME_MAP.get(iso, "unknown")

def resolve_host_to_ip(host: str) -> Optional[str]:
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        return host
    try:
        return socket.getaddrinfo(host, None)[0][4][0]
    except:
        return None

def geoip_lookup(ip: str, cache: Dict[str, Tuple[str, str]]) -> Tuple[str, str]:
    if ip in cache:
        return cache[ip]
    url = f"http://ip-api.com{ip}?fields=status,countryCode"
    try:
        with request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                iso = data.get("countryCode", "UN")
                cache[ip] = (iso, COUNTRY_NAME_MAP.get(iso, "unknown"))
                return cache[ip]
    except:
        pass
    cache[ip] = ("UN", "unknown")
    return cache[ip]

def country_from_name_heuristic(name: str) -> Tuple[str, str]:
    lower = name.lower()
    if "ru" in lower or "russia" in lower: return "RU", "russia"
    if "us" in lower or "usa" in lower: return "US", "usa"
    return "UN", "unknown"

def get_flag_for_iso(iso: str) -> str:
    return ISO_TO_FLAG.get(iso, "🏳️")

# ---------- ИМЯ ----------
def normalize_name(flag: str, index: int = None, base_name: str = DEFAULT_NAME) -> str:
    """
    Формирует имя конфига. Если индекс передан — добавляет его с символом №.
    Если индекс не передан — возвращает только флаг и базовое имя.
    """
    flag_part = f"{flag} " if flag else ""
    
    if index is None:
        return f"{flag_part}{base_name}".strip()
    
    return f"{flag_part}{base_name} №{index}".strip()


# ---------- НОРМАЛИЗАЦИЯ URI ----------
def add_repo_to_vmess(uri: str, display_name: str) -> str:
    """Обновляет название (ps) в ссылке vmess"""
    try:
        payload = uri[len("vmess://"):]
        # Добавляем == для корректного padding base64
        data = base64.b64decode(payload + "==")
        obj = json.loads(data.decode("utf-8"))
        
        # Меняем имя на новое (с флагом и номером)
        obj["ps"] = display_name
        
        # Кодируем обратно в JSON без лишних пробелов
        new_json = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        new_b64 = base64.b64encode(new_json).decode("utf-8")
        return "vmess://" + new_b64
    except Exception as e:
        logger.error(f"Ошибка при обновлении vmess: {e}")
        return uri

def add_repo_to_uri_fragment(uri: str, display_name: str) -> str:
    """Обновляет название после символа # в vless, trojan, ss"""
    try:
        # Убираем всё, что после #, и ставим новое имя
        if "#" in uri:
            base_part = uri.split("#")[0]
        else:
            base_part = uri
            
        # Кодируем имя для URL, чтобы пробелы и № не ломали ссылку
        safe_name = parse.quote(display_name)
        return f"{base_part}#{safe_name}"
    except Exception as e:
        logger.error(f"Ошибка при обновлении uri: {e}")
        return uri

# ---------- НОВАЯ ФУНКЦИЯ ОБРАБОТКИ ----------
def process_and_rename_configs(raw_lines: List[str]) -> List[str]:
    """Принимает список сырых ссылок и возвращает переименованные с флагами"""
    processed = []
    for i, line in enumerate(raw_lines, start=1):
        protocol = detect_protocol(line)
        if not protocol:
            continue
            
        # Пытаемся вытащить старое имя для поиска флага
        old_name = ""
        if protocol == "vmess":
            try:
                p = line[len("vmess://"):]
                d = json.loads(base64.b64decode(p + "==").decode('utf-8'))
                old_name = d.get("ps", "")
            except: pass
        elif "#" in line:
            old_name = parse.unquote(line.split("#")[-1])
            
        # Определяем флаг (из имени или ставим дефолт)
        flag = extract_flag_from_name(old_name) or "🏳️"
        
        # Генерируем новое название через твой normalize_name
        new_display_name = normalize_name(flag, DEFAULT_NAME, i)
        
        # Применяем переименование через твои функции
        if protocol == "vmess":
            processed.append(add_repo_to_vmess(line, new_display_name))
        else:
            processed.append(add_repo_to_uri_fragment(line, new_display_name))
            
    return processed

# Пример использования:
# ensure_dirs()
# raw_configs = ["vless://uuid@host:port?type=tcp#OldName", "vmess://eyJhZGQiOiI4LjguOC44IiwicHMiOiJ0ZXN0In0="]
# final = process_and_rename_configs(raw_configs)
# write_text_file("configs/tgk/tgk_raw.txt", final)
