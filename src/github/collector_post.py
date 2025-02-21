import asyncio
import aiohttp
import json
import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загрузка переменных окружения
load_dotenv()

# Получение токенов из переменных окружения
GH_API_TOKEN = os.getenv("GH_API_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Проверка наличия токенов API
if not GH_API_TOKEN or not GEMINI_API_KEY:
    logging.error("Необходимо установить переменные окружения GH_API_TOKEN и GEMINI_API_KEY")
    exit(1)

# Настройка модели Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")  # Используем flash-версию
    logging.info("Модель Gemini успешно инициализирована")
except Exception as e:
    logging.error(f"Ошибка инициализации модели Gemini: {e}")
    exit(1)

# Константы
PROJECTS_FILE = "data/projects.json"
PUBLISHED_POSTS_DEV_FILE = "data/published_posts_dev.json"
PUBLISHED_POSTS_HASHNODE_FILE = "data/published_posts_hashnode.json"
ARTICLE_OUTPUT_FILE = "data/article_output.json"
README_CHAR_LIMIT = 4000
DEFAULT_BRANCHES = ["main", "master"]


async def fetch_github_graphql(session, query):
    """
    Выполняет GraphQL запрос к GitHub API.
    """
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"token {GH_API_TOKEN}"}
    try:
        async with session.post(url, json={"query": query}, headers=headers) as response:
            response.raise_for_status()  # Поднимает исключение для HTTP ошибок
            return await response.json()
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при выполнении GraphQL запроса: {e}")
        return None


async def get_published_post_ids(filepath):
    """
    Получает список ID опубликованных статей из JSON файла.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Assuming the file contains a list of IDs, adjust if the structure is different
            if isinstance(data, list):
                return set(data)
            elif isinstance(data, dict) and "published_ids" in data and isinstance(data["published_ids"], list):
                return set(data["published_ids"])  # Extract from "published_ids" list
            else:
                logging.warning(f"Неверный формат файла: {filepath}. Ожидается список ID или словарь с ключом 'published_ids'.")
                return set()
    except FileNotFoundError:
        logging.warning(f"Файл не найден: {filepath}. Считаем, что нет опубликованных статей.")
        return set()
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка при чтении JSON из файла {filepath}: {e}. Считаем, что нет опубликованных статей.")
        return set()


async def get_best_repository():
    """
    Находит лучший репозиторий, исключая уже опубликованные.
    """
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            projects = json.load(f)
    except FileNotFoundError:
        logging.error(f"Файл не найден: {PROJECTS_FILE}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка при чтении JSON из файла {PROJECTS_FILE}: {e}")
        return None

    published_dev_ids = await get_published_post_ids(PUBLISHED_POSTS_DEV_FILE)
    published_hashnode_ids = await get_published_post_ids(PUBLISHED_POSTS_HASHNODE_FILE)
    published_ids = published_dev_ids.union(published_hashnode_ids)

    # Фильтруем опубликованные репозитории
    eligible_projects = [p for p in projects if p['id'] not in published_ids]

    if not eligible_projects:
        logging.info("Нет доступных репозиториев для публикации.")
        return None

    # Находим репозиторий с наивысшим quality_score
    best_repo = max(eligible_projects, key=lambda x: x['quality_score'])
    return best_repo


async def get_readme_content(session, owner, repo):
    """
    Получает содержимое README.md файла из GitHub, автоматически определяя ветку.
    """
    for branch in DEFAULT_BRANCHES:
        query = f"""
        query {{
          repository(owner: "{owner}", name: "{repo}") {{
            object(expression: "{branch}:README.md") {{
              ... on Blob {{
                text
              }}
            }}
          }}
        }}
        """
        data = await fetch_github_graphql(session, query)
        if data and 'data' in data and 'repository' in data['data'] and 'object' in data['data']['repository']:
            obj = data['data']['repository']['object']
            if obj and obj.get('text'):
                logging.info(f"README.md найден в ветке {branch} репозитория {owner}/{repo}.")
                return obj['text']
            else:
                logging.debug(f"README.md не найден в ветке {branch} репозитория {owner}/{repo}.")
        else:
            logging.error(f"Ошибка при получении README.md для {owner}/{repo} в ветке {branch}: {data}")

    logging.warning(f"README.md не найден ни в одной из веток {DEFAULT_BRANCHES} репозитория {owner}/{repo}.")
    return None


async def generate_article_from_readme(readme_content):
    """
    Генерирует статью из README.md, используя модель Gemini.
    """
    prompt = (
        "Imagine you're a tech enthusiast sharing your excitement about a cool GitHub project with fellow developers. "
        "Your mission is to write a short, engaging blog post that captures the essence of the project and its potential benefits. "
        "Think of it as a friendly conversation, explaining the project in simple terms, avoiding technical jargon where possible. "
        "The goal is to make developers say, 'Wow, I need to check this out!'\n\n"

        "Here's what the article should include:\n"
        "* **Catchy Title:**  A title that grabs attention and hints at the project's core purpose.\n"
        "* **Compelling Introduction:** Start with a hook that immediately interests the reader.  What problem does this project solve? Why is it important?\n"
        "* **Clear Explanation:** Describe the project's functionality and architecture in a way that's easy to understand, even for developers who aren't experts in the field. Break down complex concepts into digestible chunks, using analogies or real-world examples where appropriate.\n"
        "* **Benefits for Developers:** Highlight the specific advantages of using this project. How can it save them time, improve their workflow, or solve a common problem?  Be specific and practical.\n"
        "* **Well-Structured Paragraphs:** Write in clear, concise paragraphs, avoiding large blocks of text. Each paragraph should focus on a single idea or aspect of the project.\n"
        "* **Key Takeaways:** Summarize the 3-5 most important points in a concise list.  What should developers remember after reading this article?\n"
        "* **Tags:** 3-5 relevant keywords that will help people find the article (focus on core technologies and use cases).\n"
        "* **Enthusiastic Tone:** Write with passion and excitement.  Let your enthusiasm for the project shine through!\n"

        "The article must be at least 1000 characters long and written in a conversational, engaging style.\n\n"

        f"Here is the content of the README.md file:\n{readme_content[:README_CHAR_LIMIT]}\n\n"

        "Provide the response in JSON format according to the specified schema:"
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "An engaging and attention-grabbing title for the article"
                        },
                        "article": {
                            "type": "string",
                            "description": "The *main content* of the article, written in simple terms, at least 500 characters long. Explain the project's purpose, how it works, and why developers should care about it. *DO NOT* include a title, introduction, key takeaways, statistics, or any other metadata.  Structure the article with well-defined paragraphs."
                        },
                        "key_takeaways": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "A list of 3-5 key takeaways that summarize the project's most important aspects and benefits for developers."
                        },
                        "tags": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "A list of 3-5 relevant tags for the article."
                        }
                    },
                    "required": ["title", "article", "key_takeaways", "tags"]
                }
            )
        )

        try:
            response_data = json.loads(response.text)
            return response_data
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка при парсинге JSON ответа от Gemini: {e}. Текст ответа: {response.text}")
            return None

    except Exception as e:
        logging.error(f"Ошибка при вызове Gemini API: {e}")
        return None


async def main():
    """
    Основная функция, которая выполняет всю логику проекта.
    """
    async with aiohttp.ClientSession() as session:
        best_repo = await get_best_repository()
        if not best_repo:
            logging.info("Не удалось найти подходящий репозиторий для публикации.")
            return

        repo_url = best_repo['url']
        owner, repo = repo_url.split('/')[-2:]

        readme_content = await get_readme_content(session, owner, repo)
        if readme_content:
            article_data = await generate_article_from_readme(readme_content)
            if article_data:
                # Incorporate data from best_repo into article_data
                article_data["title"] = article_data.get("title", best_repo.get("name", "No Title"))  # Use Gemini title if present, else repo name
                article_data["stars"] = best_repo.get("stars", 0)
                article_data["forks"] = best_repo.get("forks", 0)
                article_data["open_issues"] = best_repo.get("open_issues", 0)
                article_data["languages"] = best_repo.get("language", "Not specified")  # Add languages
                article_data["readme_summary"] = best_repo.get("readme_summary", "")  # Add readme_summary
                # Add other fields from best_repo that you want to save
                article_data["project_id"] = best_repo.get("id")
                article_data["url"] = best_repo.get("url")
                article_data["description"] = best_repo.get("description")

                # Save to data directory in JSON format
                try:
                    with open(ARTICLE_OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(article_data, f, indent=4, ensure_ascii=False)  # This should create a valid JSON
                    logging.info(f"Статья сохранена в {ARTICLE_OUTPUT_FILE}")
                except IOError as e:
                    logging.error(f"Ошибка при записи в файл {ARTICLE_OUTPUT_FILE}: {e}")

            else:
                logging.warning("Не удалось сгенерировать статью.")
        else:
            logging.warning("Не удалось сгенерировать статью из-за отсутствия README контента.")


if __name__ == "__main__":
    asyncio.run(main())