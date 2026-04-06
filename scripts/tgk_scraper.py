import asyncio
import os
import base64
import json
import re
import urllib.parse
from telethon import TelegramClient
from telethon.sessions import StringSession  # Добавлен импорт
from utils import logger, root_path, ensure_dirs

TGK_OUTPUT = root_path("configs/tgk/tgk_raw.txt")
CHANNELS_FILE = root_path("tg_channels.txt")

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH"))
SESSION_STR = os.getenv("TG_SESSION") # Теперь это просто строка сессии

def load_channels():
    if not CHANNELS_FILE.exists():
        logger.error("tg_channels.txt not found")
        return []

    channels = []
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                channels.append(line)
    return channels

def extract_flags(text):
    if not text:
        return ""
    flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', text)
    return "".join(flags) + " " if flags else ""

def rename_config(config_url, index):
    try:
        new_base_name = f"WhiteList_TGK №{index}"
        
        if config_url.startswith("vmess://"):
            b64_data = config_url.replace("vmess://", "")
            b64_data += "=" * (-len(b64_data) % 4)
            data = json.loads(base64.b64decode(b64_data).decode('utf-8'))
            
            flag = extract_flags(data.get('ps', ''))
            data['ps'] = f"{flag}{new_base_name}".strip()
            
            new_b64 = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
            return f"vmess://{new_b64}"
            
        elif config_url.startswith(("vless://", "trojan://", "ss://")):
            if "#" in config_url:
                parts = config_url.split("#", 1)
                base_part = parts[0]
                old_name = urllib.parse.unquote(parts[1])
                flag = extract_flags(old_name)
                new_name = urllib.parse.quote(f"{flag}{new_base_name}".strip())
                return f"{base_part}#{new_name}"
            else:
                return f"{config_url}#{urllib.parse.quote(new_base_name)}"
    except Exception as e:
        logger.error(f"Error renaming config: {e}")
    return config_url

async def fetch_from_channel(client, channel):
    configs = []
    try:
        async for msg in client.iter_messages(channel, limit=1200):
            if not msg or not msg.message:
                continue
            text = msg.message.strip()
            if any(proto in text.lower() for proto in ["vmess://", "vless://", "trojan://", "ss://"]):
                for line in text.split("\n"):
                    line = line.strip()
                    if line.startswith(("vmess://", "vless://", "trojan://", "ss://")):
                        configs.append(line)
    except Exception as e:
        logger.error(f"Error reading channel {channel}: {e}")
    return configs

async def main_async():
    ensure_dirs()

    if not SESSION_STR:
        logger.error("TG_SESSION is missing in environment variables")
        return

    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("Session is invalid! Please update TG_SESSION secret.")
            return

        logger.info("Telegram client started successfully")

        channels = load_channels()
        if not channels:
            logger.error("No channels found in tg_channels.txt")
            return

        all_configs_raw = []
        for channel in channels:
            logger.info(f"Fetching from channel: {channel}")
            cfgs = await fetch_from_channel(client, channel)
            all_configs_raw.extend(cfgs)
            logger.info(f"Found {len(cfgs)} configs in {channel}")

    finally:
        await client.disconnect()

    # -----------------------------
    # УДАЛЕНИЕ ДУБЛИКАТОВ ДО РЕНЕЙМА
    # -----------------------------
    unique_configs_raw = list(dict.fromkeys(all_configs_raw))
    logger.info(f"Removed duplicates: {len(all_configs_raw)} -> {len(unique_configs_raw)}")

    # -----------------------------
    # РЕНЕЙМ + УДАЛЕНИЕ ДУБЛИКАТОВ ПОСЛЕ РЕНЕЙМА
    # -----------------------------
    all_configs = []
    seen = set()

    for i, cfg in enumerate(unique_configs_raw, start=1):
        renamed = rename_config(cfg, i)

        cfg_key = str(renamed)
        if cfg_key in seen:
            logger.info(f"Duplicate after rename skipped: {cfg_key}")
            continue

        seen.add(cfg_key)
        all_configs.append(renamed)

    header = [
        "# profile-title: Gh0st_WhiteList [TGK]",
        "# profile-web-page: https://github.com",
        "# support-url: https://t.me",
        "# profile-update-interval: 1",
        "# subscription-userinfo: upload=0; download=0; total=854347202560000; expire=0",
        f"# Всего рабочих: {len(all_configs)}",
        ""
    ]

    with open(TGK_OUTPUT, "w", encoding="utf-8") as f:
        for line in header:
            f.write(line + "\n")
        for line in all_configs:
            f.write(line + "\n")

    logger.info(f"Saved {len(all_configs)} TG configs to {TGK_OUTPUT}")

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
