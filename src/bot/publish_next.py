import json
import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import PeerChannel
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)

async def publish_post(client, post, session, channel_id):
    """Публикует пост в указанный канал Telegram"""
    try:
        channel = PeerChannel(int(channel_id.replace("-100", "")))

        # Логирование содержимого перед отправкой
        logging.info(f"Preparing to send message to channel {channel_id}:")
        logging.info(f"Content: {post['content']}")

        if post.get("media_url"):
            async with session.get(post["media_url"]) as response:
                if response.status == 200:
                    temp_file = "temp_image.jpg"
                    with open(temp_file, "wb") as f:
                        f.write(await response.read())

                    await client.send_file(
                        channel,
                        temp_file,
                        caption=post["content"],
                        parse_mode='html',
                        force_document=False,
                        link_preview=False  # Отключаем предпросмотр ссылок
                    )

                    os.remove(temp_file)
                else:
                    logging.error("Failed to download media, skipping post.")
                    return False
        else:
            await client.send_message(
                channel,
                post["content"],
                parse_mode='html',
                link_preview=False  # Отключаем предпросмотр ссылок
            )
        return True
    except Exception as e:
        logging.error(f"Error publishing post to channel {channel_id}: {e}")
        return False

async def main():
    try:
        queue_dir = "data/queue"
        if not os.path.exists(queue_dir):
            logging.info("No queue directory found")
            return

        posts = sorted([f for f in os.listdir(queue_dir) if f.endswith('.json')])
        if not posts:
            logging.info("No posts in queue")
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

                # Публикация в дополнительные каналы, только если основной успешен
                if success:
                    additional_channels = os.getenv("ADDITIONAL_CHANNELS", "").split(",")
                    channel_names = json.loads(os.getenv("CHANNEL_NAMES", "{}"))

                    for channel_key in additional_channels:
                        channel_config = channel_names.get(channel_key.strip())
                        if channel_config:
                            channel_id = channel_config.get("id")
                            if channel_id:
                                success = await publish_post(client, post, session, channel_id)
                                if not success:
                                    break

                # Удаление поста из очереди, если публикация не удалась
                if not success:
                    logging.info(f"Removing post {next_post_file} due to publication failure.")
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
                logging.info(f"Successfully processed and removed {next_post_file}")

    except Exception as e:
        logging.error(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())
