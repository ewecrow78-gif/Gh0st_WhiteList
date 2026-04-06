import json
import os
import datetime
from utils import root_path, logger

# Пути к файлам
README_PATH = root_path("README.md")
STATS_PATH = root_path("configs/stats.json")
ALIVE_PATH = root_path("configs/alive.json")
STATUS_JSON_PATH = root_path("status.json") # Файл для бейджа

def safe_load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None

def main():
    logger.info("Генерация README и обновление статуса...")

    # Загружаем данные
    stats = safe_load_json(STATS_PATH) or {"total": 0, "by_country": {}, "by_protocol": {}}
    alive = safe_load_json(ALIVE_PATH) or []
    
    total_count = stats.get("total", 0)
    alive_count = len(alive)
    update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Создаем status.json для динамического бейджа
    status_data = {
        "count": alive_count,
        "last_update": update_time
    }
    with open(STATUS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)

    # 1. Готовим текст для стран
    by_country = stats.get("by_country", {})
    country_lines = []
    if by_country:
        sorted_countries = sorted(by_country.items(), key=lambda x: x[1], reverse=True)[:15]
        for iso, count in sorted_countries:
            country_lines.append(f"- **{iso}** — {count}")
    else:
        country_lines.append("_Нет данных_")
    countries_text = "\n".join(country_lines)

    # 2. Готовим текст для протоколов
    by_protocol = stats.get("by_protocol", {})
    proto_lines = []
    if by_protocol:
        sorted_protos = sorted(by_protocol.items(), key=lambda x: x[1], reverse=True)
        for proto, count in sorted_protos:
            proto_lines.append(f"- **{proto.upper()}** — {count}")
    else:
        proto_lines.append("_Нет данных_")
    protos_text = "\n".join(proto_lines)

    # Собираем финальный README с правильными ссылками на бейджи
    readme_content = f"""<div align="center">

# 🏳️ Gh0st_WhiteList 🏳️
**Элитный агрегатор и чекер проверенных VPN-конфигураций**

![GitHub last commit](https://shields.io)
![Update](https://shields.io)
![Status](https://shields.io)

---

### ⚡ Текущий статус сети



| Параметр | Значение |
| :--- | :--- |
| **Всего найдено** | `{total_count}` |
| **Рабочих узлов** | `{alive_count}` |
| **Последнее обновление** | `{update_time}` |
| **Оптимизация** | ✅ Специально для РФ |

---

### 🌐 Ссылка на подписку (Subscription)
`https://githubusercontent.com`

</div>

---

## 📊 Статистика

<details>
<summary><b>🌍 Развернуть статистику по странам (Топ-15)</b></summary>

{countries_text}
</details>

<details>
<summary><b>🔌 Развернуть статистику по протоколам</b></summary>

{protos_text}
</details>

---

## 🛠️ Инструкции по настройке

### 🤖 v2rayNG (Android)
1. Скопируйте ссылку на подписку выше.
2. Откройте приложение ➔ Меню ➔ **Группы подписок**.
3. Нажмите **+** ➔ Введите любое имя и вставьте ссылку.
4. Вернитесь на главный экран ➔ Три точки ➔ **Обновить подписку**.

### ⚡ Hiddify / Happ (Все платформы)
1. Нажмите **Новый профиль** (или **+**).
2. Выберите **Добавить из URL** (Add from URL).
3. Вставьте ссылку и нажмите **Добавить**.

### 🍎 V2Box / Shadowrocket (iOS)
1. Вкладка **Configs** ➔ Нажмите **+** в углу.
2. Выберите **Add Subscription**.
3. Введите имя `Gh0st` и вставьте ссылку.
4. Нажмите **Update** (круговая стрелка).

---

## 💎 Почему наш лист лучше?
> [!IMPORTANT]
> Мы не просто собираем ссылки, мы их **фильтруем**.

* **Чистка:** Автоматическое удаление нерабочих узлов каждые 30 минут.
* **Порядок:** Каждый сервер имеет флаг страны и порядковый номер.
* **Скорость:** Проверка TCP-отклика перед публикацией.

---

## 📬 Контакты
Telegram: [👉 t.me/whitelistGh0st](https://t.me)

<p align="center">
  <i>Обновлено автоматически: {update_time} (UTC)</i>
</p>
"""

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme_content.strip() + "\n")

    logger.info("README.md и status.json успешно обновлены!")

if __name__ == "__main__":
    main()
