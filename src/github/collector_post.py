import asyncio
import aiohttp
import json
import os
import logging
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

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
    sys.exit(1)

# Настройка клиента Gemini
try:
    client_gemini = genai.Client(api_key=GEMINI_API_KEY)
    logging.info("Модель Gemini успешно инициализирована")
except Exception as e:
    logging.error(f"Ошибка инициализации модели Gemini: {e}")
    sys.exit(1)

# Модели Gemini
GEMINI_MODEL_ARTICLE = "gemini-2.5-flash"
GEMINI_MODEL_LITE = "gemini-2.5-flash-lite"

# Константы
PROJECTS_FILE = "data/projects.json"
PUBLISHED_POSTS_DEV_FILE = "data/published_posts_dev.json"
PUBLISHED_POSTS_HASHNODE_FILE = "data/published_posts_hashnode.json"
ARTICLE_OUTPUT_FILE = "data/article_output.json"
README_CHAR_LIMIT = 4000

# Варианты имён README файла (разный регистр и расширения)
README_FILENAMES = [
    "README.md",
    "readme.md",
    "Readme.md",
    "README.MD",
    "README.rst",
    "readme.rst",
    "README.txt",
    "readme.txt",
    "README",
    "readme",
]

# Лимит: 5 запросов в минуту
GEMINI_RPM_LIMIT = 5
GEMINI_MIN_INTERVAL = 60.0 / GEMINI_RPM_LIMIT  # 12 секунд между запросами
_last_gemini_call_time = 0.0


def _wait_for_gemini_rate_limit():
    """
    Блокирующее ожидание, чтобы не превысить лимит 5 запросов в минуту.
    """
    global _last_gemini_call_time
    elapsed = time.time() - _last_gemini_call_time
    wait_time = GEMINI_MIN_INTERVAL - elapsed
    if wait_time > 0:
        logging.info(f"Rate limit: ожидаем {wait_time:.1f}с перед запросом к Gemini...")
        time.sleep(wait_time)
    _last_gemini_call_time = time.time()


async def fetch_github_graphql(session, query):
    """
    Выполняет GraphQL запрос к GitHub API.
    """
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"token {GH_API_TOKEN}"}
    try:
        async with session.post(url, json={"query": query}, headers=headers) as response:
            response.raise_for_status()
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
            if isinstance(data, list):
                return set(data)
            elif isinstance(data, dict) and "published_ids" in data and isinstance(data["published_ids"], list):
                return set(data["published_ids"])
            else:
                logging.warning(f"Неверный формат файла: {filepath}. Ожидается список ID или словарь с ключом 'published_ids'.")
                return set()
    except FileNotFoundError:
        logging.warning(f"Файл не найден: {filepath}. Считаем, что нет опубликованных статей.")
        return set()
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка при чтении JSON из файла {filepath}: {e}. Считаем, что нет опубликованных статей.")
        return set()


async def get_default_branch(session, owner, repo):
    """
    Возвращает имя ветки по умолчанию репозитория через GitHub GraphQL API.
    Если получить не удалось — возвращает None.
    """
    query = f"""
    query {{
      repository(owner: "{owner}", name: "{repo}") {{
        defaultBranchRef {{
          name
        }}
      }}
    }}
    """
    data = await fetch_github_graphql(session, query)
    try:
        branch = data["data"]["repository"]["defaultBranchRef"]["name"]
        logging.info(f"Ветка по умолчанию для {owner}/{repo}: {branch}")
        return branch
    except (TypeError, KeyError):
        logging.warning(f"Не удалось получить ветку по умолчанию для {owner}/{repo}. Будет использован fallback.")
        return None


async def get_readme_content(session, owner, repo):
    """
    Получает содержимое README из GitHub, перебирая ветки и варианты имён файла.

    Алгоритм:
      1. Запрашиваем defaultBranchRef.name через GraphQL.
      2. Формируем список веток для перебора: сначала ветка по умолчанию,
         затем fallback-варианты ["main", "master"] (без дубликатов).
      3. Для каждой ветки перебираем все варианты имён README файла.
      4. Возвращаем первый найденный текст.
    """
    # Шаг 1: узнаём ветку по умолчанию
    default_branch = await get_default_branch(session, owner, repo)

    # Шаг 2: строим список веток без дубликатов
    fallback_branches = ["main", "master"]
    branches_to_try = []
    if default_branch:
        branches_to_try.append(default_branch)
    for b in fallback_branches:
        if b not in branches_to_try:
            branches_to_try.append(b)

    # Шаг 3: перебираем ветки и варианты имён файла
    for branch in branches_to_try:
        for filename in README_FILENAMES:
            query = f"""
            query {{
              repository(owner: "{owner}", name: "{repo}") {{
                object(expression: "{branch}:{filename}") {{
                  ... on Blob {{
                    text
                  }}
                }}
              }}
            }}
            """
            data = await fetch_github_graphql(session, query)

            if not data:
                logging.debug(f"Пустой ответ для {owner}/{repo} ветка='{branch}' файл='{filename}'")
                continue

            try:
                obj = data["data"]["repository"]["object"]
                if obj and obj.get("text"):
                    logging.info(f"README найден: '{filename}' в ветке '{branch}' репозитория {owner}/{repo}.")
                    return obj["text"]
            except (TypeError, KeyError):
                logging.debug(f"Не удалось разобрать ответ для {owner}/{repo} ветка='{branch}' файл='{filename}'")
                continue

    logging.warning(
        f"README не найден ни в одной из веток {branches_to_try} репозитория {owner}/{repo}."
    )
    return None


async def generate_article_from_readme(readme_content):
    """
    Генерирует статью из README, используя модель Gemini.
    При ошибках 503/429 делает retry с экспоненциальной задержкой.
    """
    prompt = (
        "Imagine you're a tech enthusiast sharing your excitement about a cool GitHub project with fellow developers. "
        "Your mission is to write a short, engaging blog post that captures the essence of the project and its potential benefits. "
        "Think of it as a friendly conversation, explaining the project in simple terms, avoiding technical jargon where possible. "
        "The goal is to make developers say, 'Wow, I need to check this out!'\n\n"

        "Here's what the article should include:\n"
        "* **Catchy Title:**  A title that grabs attention and hints at the project's core purpose.\n"
        "* **Compelling Introduction:** Start with a hook that immediately interests the reader. What problem does this project solve? Why is it important?\n"
        "* **Clear Explanation:** Describe the project's functionality and architecture in a way that's easy to understand, even for developers who aren't experts in the field. Break down complex concepts into digestible chunks, using analogies or real-world examples where appropriate.\n"
        "* **Benefits for Developers:** Highlight the specific advantages of using this project. How can it save them time, improve their workflow, or solve a common problem? Be specific and practical.\n"
        "* **Well-Structured Paragraphs:** Write in clear, concise paragraphs, avoiding large blocks of text. Each paragraph should focus on a single idea or aspect of the project.\n"
        "* **Key Takeaways:** Summarize the 3-5 most important points in a concise list. What should developers remember after reading this article?\n"
        "* **Tags:** 3-5 relevant keywords that will help people find the article (focus on core technologies and use cases).\n"
        "* **Enthusiastic Tone:** Write with passion and excitement. Let your enthusiasm for the project shine through!\n\n"

        "The article must be at least 1000 characters long and written in a conversational, engaging style.\n\n"

        f"Here is the content of the README file:\n{readme_content[:README_CHAR_LIMIT]}\n\n"

        "Provide the response in JSON format according to the specified schema:"
    )

    max_retries = 3
    retry_delays = [30, 60, 120]

    for attempt in range(max_retries):
        try:
            _wait_for_gemini_rate_limit()

            response = client_gemini.models.generate_content(
                model=GEMINI_MODEL_ARTICLE,
                contents=prompt,
                config=types.GenerateContentConfig(
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
                                "description": "The *main content* of the article, written in simple terms, at least 500 characters long."
                            },
                            "key_takeaways": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "A list of 3-5 key takeaways."
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "A list of 3-5 relevant tags."
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
            error_str = str(e)
            is_retryable = any(code in error_str for code in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"])

            if is_retryable and attempt < max_retries - 1:
                delay = retry_delays[attempt]
                logging.warning(
                    f"Gemini временно недоступен (попытка {attempt + 1}/{max_retries}): {e}. "
                    f"Повторяем через {delay}с..."
                )
                time.sleep(delay)
                continue
            else:
                logging.error(f"Ошибка при вызове Gemini API: {e}")
                return None

    logging.warning(f"Все {max_retries} попытки исчерпаны для generate_article_from_readme. Возвращаем None.")
    return None


async def main():
    """
    Основная функция. Перебирает репозитории по убыванию quality_score,
    пропускает те, у которых нет README или Gemini не смог сгенерировать статью.
    Останавливается при первом успешном результате.
    """
    # Загружаем список проектов
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            projects = json.load(f)
    except FileNotFoundError:
        logging.error(f"Файл не найден: {PROJECTS_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка при чтении JSON из файла {PROJECTS_FILE}: {e}")
        sys.exit(1)

    if not projects:
        logging.warning("Файл projects.json пуст — нет данных для публикации. Останавливаем пайплайн.")
        sys.exit(1)

    # Загружаем ID уже опубликованных постов
    published_dev_ids = await get_published_post_ids(PUBLISHED_POSTS_DEV_FILE)
    published_hashnode_ids = await get_published_post_ids(PUBLISHED_POSTS_HASHNODE_FILE)
    published_ids = published_dev_ids.union(published_hashnode_ids)

    # Фильтруем и сортируем по quality_score (лучшие — первые)
    eligible_projects = sorted(
        [p for p in projects if p.get("id") not in published_ids],
        key=lambda x: x.get("quality_score", 0),
        reverse=True
    )

    if not eligible_projects:
        logging.info("Нет доступных репозиториев для публикации (все уже опубликованы).")
        sys.exit(1)

    logging.info(f"Найдено {len(eligible_projects)} кандидатов для публикации.")

    async with aiohttp.ClientSession() as session:
        for index, best_repo in enumerate(eligible_projects):
            repo_url = best_repo.get("url", "")
            if not repo_url:
                logging.warning(f"[{index + 1}/{len(eligible_projects)}] Репозиторий без URL, пропускаем.")
                continue

            try:
                owner, repo = repo_url.rstrip("/").split("/")[-2:]
            except ValueError:
                logging.warning(f"[{index + 1}/{len(eligible_projects)}] Некорректный URL репозитория: {repo_url}, пропускаем.")
                continue

            logging.info(f"[{index + 1}/{len(eligible_projects)}] Обрабатываем репозиторий: {owner}/{repo}")

            # Пробуем получить README
            readme_content = await get_readme_content(session, owner, repo)
            if not readme_content:
                logging.warning(f"README не найден для {owner}/{repo}, пробуем следующий репозиторий...")
                continue

            # Генерируем статью через Gemini
            article_data = await generate_article_from_readme(readme_content)
            if not article_data:
                logging.warning(f"Gemini не смог сгенерировать статью для {owner}/{repo}, пробуем следующий репозиторий...")
                continue

            # Собираем итоговый объект
            article_data["title"] = article_data.get("title", best_repo.get("name", "No Title"))
            article_data["stars"] = best_repo.get("stars", 0)
            article_data["forks"] = best_repo.get("forks", 0)
            article_data["open_issues"] = best_repo.get("open_issues", 0)
            article_data["languages"] = best_repo.get("language", "Not specified")
            article_data["readme_summary"] = best_repo.get("readme_summary", "")
            article_data["project_id"] = best_repo.get("id")
            article_data["url"] = best_repo.get("url")
            article_data["description"] = best_repo.get("description")

            # Сохраняем результат
            try:
                os.makedirs(os.path.dirname(ARTICLE_OUTPUT_FILE), exist_ok=True)
                with open(ARTICLE_OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(article_data, f, indent=4, ensure_ascii=False)
                logging.info(f"Статья успешно сохранена в {ARTICLE_OUTPUT_FILE} для репозитория {owner}/{repo}")
            except IOError as e:
                logging.error(f"Ошибка при записи в файл {ARTICLE_OUTPUT_FILE}: {e}")
                sys.exit(1)

            # Успешно завершаем
            return

    # Если ни один репозиторий не подошёл
    logging.warning("Ни для одного репозитория не удалось создать статью. Останавливаем пайплайн.")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
