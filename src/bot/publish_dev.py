import json
import os
import requests
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
load_dotenv()
DEV_API_KEY = os.getenv("DEV_API_KEY")

def load_published_posts():
    try:
        with open("data/published_posts_dev.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_published_post(project_id):
    published_posts = load_published_posts()
    if project_id not in published_posts:
        published_posts.append(project_id)
        with open("data/published_posts_dev.json", "w") as f:
            json.dump(published_posts, f)

def publish_to_dev(article_data):
    """Publishes an article to DEV.to using the DEV API."""
    if "article" in article_data:
        article = article_data["article"]
    else:
        article = article_data

    project_id = article.get("project_id")
    if not project_id:
        logging.error("No project ID found in the article data.")
        return

    published_posts = load_published_posts()
    if project_id in published_posts:
        logging.info(f"Article with project ID {project_id} has already been published. Skipping.")
        return

    api_endpoint = "https://dev.to/api/articles"
    headers = {
        "Content-Type": "application/json",
        "api-key": DEV_API_KEY,
    }
    
    tags = ", ".join(article["tags"]) if isinstance(article["tags"], list) else article["tags"]
    
    payload = {
        "article": {
            "title": article["title"],
            "body_markdown": article["body_markdown"],
            "published": True,
            "tags": tags,
            "description": article.get("description", "No description provided")
        }
    }

    logging.info("Request Payload:")
    logging.info(json.dumps(payload, indent=4))

    logging.info("Data being sent to DEV.to API:")
    logging.info(f"Title: {payload['article']['title']}")
    logging.info(f"Body Markdown (first 200 chars): {payload['article']['body_markdown'][:200]}...")
    logging.info(f"Tags: {payload['article']['tags']}")
    logging.info(f"Description: {payload['article']['description']}")

    try:
        response = requests.post(api_endpoint, headers=headers, json=payload)
        if response.status_code == 201:
            logging.info("Article successfully created on DEV.to!")
            article_url = response.json().get("url")
            logging.info(f"Article URL: {article_url}")
            save_published_post(project_id)
        else:
            logging.error(f"Failed to create article. Status code: {response.status_code}")
            logging.error(f"Response content: {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred during the API request: {e}")

def main():
    try:
        with open("data/dev_post.json", "r", encoding="utf-8") as f:
            article_data = json.load(f)
    except FileNotFoundError:
        print("Error: data/dev_post.json not found. Please run formated.py first.")
        return

    if not DEV_API_KEY:
        print("Error: DEV_API_KEY not found in environment variables. Set it before running this script.")
        return

    publish_to_dev(article_data)

if __name__ == "__main__":
    main()
