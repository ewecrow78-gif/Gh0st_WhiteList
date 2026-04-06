import asyncio
import os
from typing import List

from utils import (
    VPNConfig,
    logger,
    write_text_file,
    write_json_file,
    root_path,
    normalize_name,
    add_repo_to_vmess,
    add_repo_to_uri_fragment
)

CONFIGS_JSON = root_path("configs/configs.json")


async def tcp_ping(host: str, port: int, timeout: float = 3.0) -> float | None:
    import time
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return (time.perf_counter() - start) * 1000
    except:
        return None


async def check_config(cfg: VPNConfig) -> VPNConfig | None:
    latency = await tcp_ping(cfg.host, cfg.port)
    if latency is None:
        return None
    cfg.latency_ms = latency
    return cfg


async def run_checks(configs: List[VPNConfig], concurrency: int = 100) -> List[VPNConfig]:
    sem = asyncio.Semaphore(concurrency)
    alive: List[VPNConfig] = []

    async def worker(cfg: VPNConfig):
        async with sem:
            res = await check_config(cfg)
            if res:
                alive.append(res)

    tasks = [asyncio.create_task(worker(cfg)) for cfg in configs]
    await asyncio.gather(*tasks)
    return alive


def load_configs() -> List[VPNConfig]:
    import json

    if not CONFIGS_JSON.exists():
        logger.error("configs.json not found, skipping checker")
        return []

    with open(CONFIGS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [VPNConfig(**item) for item in data]


def main():
    logger.info("Starting checker...")

    configs = load_configs()
    if not configs:
        logger.error("No configs to check")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    alive = loop.run_until_complete(run_checks(configs))
    loop.close()

    # 1. Сортируем по пингу (от быстрых к медленным)
    alive.sort(key=lambda c: c.latency_ms or 999999)

    # 2. Нумеруем сервера и обновляем их названия внутри ссылок
    for i, cfg in enumerate(alive, start=1):
        # Внутренности цикла должны быть смещены еще на 4 пробела вправо
        cfg.name = normalize_name(cfg.flag, i)
        if cfg.protocol == "vmess":
            cfg.raw = add_repo_to_vmess(cfg.raw, cfg.name)
        else:
            cfg.raw = add_repo_to_uri_fragment(cfg.raw, cfg.name)
    # 3. Записываем обновленные данные в файлы
    
    # alive.txt
    write_text_file(
        "configs/alive.txt",
        [c.raw for c in alive],
        scope="ALIVE",
        alive_count=len(alive),
    )

    # top_fast.txt
    write_text_file(
        "configs/top_fast.txt",
        [c.raw for c in alive[:50]],
        scope="TOP_FAST",
        alive_count=len(alive[:50]),
    )

    # Обновляем JSON файлы новыми именами и задержками
    write_json_file("configs/alive.json", [c.__dict__ for c in alive])
    write_json_file("configs/configs.json", [c.__dict__ for c in configs])

    logger.info(f"Alive servers: {len(alive)}")
    logger.info("Checker finished")


if __name__ == "__main__":
    main()
