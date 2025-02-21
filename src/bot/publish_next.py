import json
import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import PeerChannel
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds

async def publish_post(client, post, session, channel_id):
    """Публикует пост в указанный канал Telegram"""
    try:
        channel = PeerChannel(int(channel_id.replace("-100", "")))

        # Логирование содержимого перед отправкой
        logging.info(f"Подготовка к отправке сообщения в канал {channel_id}:")
        logging.info(f"Содержимое: {post['content']}")

        media_file = None  # Инициализируем media_file в None
        if post.get("media_url"):
            for attempt in range(MAX_RETRIES):
                try:
                    async with session.get(post["media_url"]) as response:
                        if response.status == 200:
                            media_file = "temp_image.jpg"
                            with open(media_file, "wb") as f:
                                f.write(await response.read())
                            break  # Загрузка успешна, выходим из цикла повтора
                        else:
                            logging.error(f"Попытка {attempt + 1} не удалась: Загрузка медиа из {post['media_url']}. Статус: {response.status}, Текст: {await response.text()}")
                except aiohttp.ClientError as e:
                    logging.error(f"Попытка {attempt + 1} не удалась: Загрузка медиа из {post['media_url']}. Ошибка клиента: {e}")

                if attempt < MAX_RETRIES - 1:
                    logging.info(f"Повторная попытка через {RETRY_DELAY} секунд...")
                    await asyncio.sleep(RETRY_DELAY)  # Используем asyncio.sleep для асинхронной задержки

            if media_file:
                # Отправляем медиа с подписью
                try:
                    await client.send_file(
                        channel,
                        media_file,
                        caption=post["content"],
                        parse_mode='html',
                        force_document=False,
                        link_preview=False  # Отключаем предпросмотр ссылок
                    )
                except Exception as e:
                    logging.error(f"Ошибка при отправке медиа с подписью в канал {channel_id}: {e}")
                    if media_file and os.path.exists(media_file):  # Check if file exists before removing
                        os.remove(media_file)
                    return False
                finally:
                    if media_file and os.path.exists(media_file):  # Check if file exists before removing
                        os.remove(media_file)  # Очищаем временный файл

            else:
                logging.warning(f"Не удалось загрузить медиа после {MAX_RETRIES} попыток, отправляем только текст.")
                await client.send_message(
                    channel,
                    post["content"],
                    parse_mode='html',
                    link_preview=False  # Отключаем предпросмотр ссылок
                )

        else:
            await client.send_message(
                channel,
                post["content"],
                parse_mode='html',
                link_preview=False  # Отключаем предпросмотр ссылок
            )
        return True
    except Exception as e:
        logging.error(f"Ошибка при публикации поста в канал {channel_id}: {e}")
        return False

async def main():
    try:
        queue_dir = "data/queue"
        if not os.path.exists(queue_dir):
            logging.info("Директория очереди не найдена")
            return

        posts = sorted([f for f in os.listdir(queue_dir) if f.endswith('.json')])
        if not posts:
            logging.info("В очереди нет постов")
            return

        next_post_file = posts[0]
        next_post_path = os.path.join(queue_dir, next_post_file)
        with open(next_post_path, "r", encoding="utf-8") as f:
            post = json.load(f)

        client = TelegramClient(
            StringSession(os.getenv("TELEGRAM_SESSION_STRING")),
            int(os.getenv("TELEGRAM_API_ID")),
            os.getenv("TELEGRAM_API_HASH")
        )

        async with client:
            async with aiohttp.ClientSession() as session:
                # Публикация в основной канал
                main_channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
                success = False
                if main_channel_id:
                    success = await publish_post(client, post, session, main_channel_id)

                # Удаление поста из очереди, если публикация не удалась
                if not success:
                    logging.info(f"Удаление поста {next_post_file} из-за неудачи при публикации.")
                else:
                    # Обновление списка опубликованных постов
                    published = []
                    try:
                        with open("data/published_posts.json", "r", encoding="utf-8") as f:
                            published = json.load(f)
                    except FileNotFoundError:
                        pass

                    published.append(post["project_id"])
                    with open("data/published_posts.json", "w", encoding="utf-8") as f:
                        json.dump(published, f)

                os.remove(next_post_path)
                logging.info(f"Успешно обработан и удален {next_post_file}")

    except Exception as e:
        logging.error(f"Ошибка в main: {e}")

if __name__ == "__main__":
    asyncio.run(main())
