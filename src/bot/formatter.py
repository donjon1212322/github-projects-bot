import json
import random
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')

MAX_TELEGRAM_CAPTION_LENGTH = 1024  # Максимальная длина подписи в Telegram

def slice_filter(value, count):
    """Фильтр для обрезки списка до определенного количества элементов"""
    return value[:count]

def format_post(project, template_env, additional_channels=None):
    try:
        # Проверяем наличие media_url сразу
        if not project.get("media_urls"):
            logging.info(f"Skipping project {project.get('name', 'unknown')}: no media URL")
            return None
        template = template_env.get_template("telegram_template.md")

        # Форматируем ключевые особенности как список
        key_features = project.get("key_features", [])
        if isinstance(key_features, str):
            try:
                key_features = eval(key_features) if key_features.startswith('[') else [key_features]
            except:
                key_features = [key_features]

        # Обработка topics
        topics = project.get("topics", [])
        if isinstance(topics, str):
            topics = [t.strip() for t in topics.split(',')]
        elif isinstance(topics, list) and len(topics) > 0 and isinstance(topics[0], list):
            topics = topics[0]  # Берем первый список, если topics - список списков

        # Форматируем description
        description = (project.get("description") or "").strip()
        if description.endswith('...'):
            description = description[:-3]

        # Получаем конфигурацию каналов
        try:
            channel_names = json.loads(os.getenv("CHANNEL_NAMES", "{}"))
        except json.JSONDecodeError:
            logging.warning("Invalid CHANNEL_NAMES JSON in environment variables. Using empty dict.")
            channel_names = {}

        # Формируем строку дополнительных каналов
        additional_channels_str = ""
        if additional_channels:
            links = []
            for channel_key in additional_channels:
                channel_info = channel_names.get(channel_key.strip(), {})
                channel_name = channel_info.get("name", channel_key)
                channel_icon = channel_info.get("icon", "")
                links.append(f"<a href='https://t.me/{channel_key.strip()}'>{channel_icon} {channel_name}</a>")
            additional_channels_str = " | ".join(links)

        context = {
            "emoji": random.choice(["🚀", "💡", "✨", "🔥", "🌟"]),
            "project_name": project.get("name", "Unknown Project"),
            "language": project.get("language", "Not specified"),
            "description": description,
            "stars": f"{project.get('stars', 0):,}".replace(',', ' '),
            "forks": f"{project.get('forks', 0):,}".replace(',', ' '),
            "open_issues": f"{project.get('open_issues', 0):,}".replace(',', ' '),
            "topics": topics,
            "last_updated": datetime.fromisoformat(project.get('updated_at', datetime.now().isoformat()).replace('Z', '')).strftime('%Y-%m-%d'),
            "url": project.get("url", ""),
            "homepage": project.get("homepage") or "",
            "demo_url": project.get("demo_url") or "",
            "readme_summary": (project.get("readme_summary") or "").strip(),
            "key_features": key_features,
            "primary_use_case": (project.get("primary_use_case") or "").strip(),
            "additional_channels": additional_channels_str.strip(),
            "channel_names": channel_names,
            "languages": project.get("languages", "Not specified")
        }

        # Получаем медиа URL (теперь мы уверены что он есть)
        media_url = project["media_urls"][0]

        # Форматируем контент
        content = template.render(context)

        # Убираем двойные пустые строки и лишние пробелы
        content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())

        # Обрезаем key_features, если необходимо
        while len(content) > MAX_TELEGRAM_CAPTION_LENGTH and key_features:
            key_features.pop()
            context["key_features"] = key_features  # Обновляем context с обрезанными key_features
            content = template.render(context)
            content = '\n'.join(line.strip() for line in content.split('\n') if line.strip()) # Reformat after trimming

        if len(content) > MAX_TELEGRAM_CAPTION_LENGTH:
            logging.warning(f"Skipping project {project.get('name', 'unknown')}: Content too long even after removing all key features.")
            return None # Skip the post if key_features trimming wasn't enough

        return {
            "content": content,
            "media_url": media_url
        }
    except Exception as e:
        logging.error(f"Error formatting post for project {project.get('name', 'unknown')}: {str(e)}")
        return None

def main():
    """Основная функция для форматирования контента."""
    try:
        # Загружаем проекты
        with open("data/projects.json", "r", encoding="utf-8") as f:
            projects = json.load(f)
        if not projects:
            logging.info("No projects found in data/projects.json. Skipping formatting.")
            return

        # Настройка окружения Jinja2
        template_path = os.path.join(os.getcwd(), "data", "templates")
        template_env = Environment(loader=FileSystemLoader(template_path))

        # Добавляем фильтр slice
        template_env.filters['slice'] = slice_filter

        # Получаем дополнительные каналы из переменной окружения
        additional_channels = os.getenv("ADDITIONAL_CHANNELS", "").split(",")
        additional_channels = [channel.strip() for channel in additional_channels if channel.strip()]

        posts = []
        for project in projects:
            post = format_post(project, template_env, additional_channels)
            if post:  # Добавляем пост только если он успешно отформатирован и имеет медиа
                posts.append({
                    "project_id": project["id"],
                    "content": post["content"],
                    "media_url": post["media_url"],
                    "platform": "telegram",
                    "quality_score": project.get("quality_score", 0)
                })

        if posts:
            # Создаем директорию data если её нет
            os.makedirs("data", exist_ok=True)

            # Сохраняем отформатированные посты
            with open("data/posts.json", "w", encoding="utf-8") as f:
                json.dump(posts, f, indent=4, ensure_ascii=False)
            logging.info(f"Successfully formatted and saved {len(posts)} posts to data/posts.json")
        else:
            logging.info("No posts to format. Skipping writing to data/posts.json")
    except FileNotFoundError:
        logging.error("Error: data/projects.json not found. Please ensure the file exists.")
    except json.JSONDecodeError:
        logging.error("Error: Invalid JSON format in data/projects.json")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()