import json
import os
from jinja2 import Environment, FileSystemLoader

def process_tags(tags):
    # Разделяем теги, если они в строке
    if isinstance(tags, str):
        tags = tags.split(',')
    
    # Обрабатываем каждый тег
    processed_tags = []
    for tag in tags:
        # Удаляем лишние пробелы
        tag = tag.strip()
        # Берем только первое слово из тега
        tag = tag.split()[0]
        # Удаляем любые не-алфавитные символы
        tag = ''.join(c for c in tag if c.isalnum())
        # Приводим к нижнему регистру
        tag = tag.lower()
        if tag:
            processed_tags.append(tag)
    
    # Ограничиваем количество тегов до 4
    return processed_tags[:4]

def format_article_markdown(data):
    """Formats the article content using the Markdown template."""
    env = Environment(loader=FileSystemLoader('data/templates'))
    template = env.get_template('dev_template.md')

    # Обрабатываем теги
    tags = process_tags(data['tags'])
    
    # Убедимся, что у нас есть все необходимые данные
    context = {
        'title': data['title'],
        'tags': tags,
        'readme_summary': data.get('readme_summary', ''),
        'key_takeaways': data.get('key_takeaways', []),
        'stars': data.get('stars', 0),
        'forks': data.get('forks', 0),
        'open_issues': data.get('open_issues', 0),
        'languages': data.get('languages', ''),
        'article': data['article'],
        'url': data.get('url', '')
    }

    # Рендерим шаблон
    formatted_content = template.render(context)
    return formatted_content

def main():
    try:
        with open("data/article_output.json", "r", encoding="utf-8") as f:
            article_data = json.load(f)
    except FileNotFoundError:
        print("Error: data/article_output.json not found. Please run post_generik.py first.")
        return

    formatted_content = format_article_markdown(article_data)

    dev_post_data = {
        "article": {
            "title": article_data["title"],
            "body_markdown": formatted_content,
            "tags": process_tags(article_data["tags"]),
            "description": article_data.get("description", "No description provided"),
            "published": False,
            "project_id": article_data.get("project_id", "")  # Добавляем идентификатор проекта
        }
    }

    output_path = os.path.join("data", "dev_post.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dev_post_data, f, indent=4, ensure_ascii=False)

    print(f"Formatted content saved to {output_path}")
    print("--------------------------------------")
    print("Data being sent to DEV.to:")
    print(f"Title: {dev_post_data['article']['title']}")
    print(f"Body Markdown: {dev_post_data['article']['body_markdown'][:200]}...")
    print(f"Tags: {dev_post_data['article']['tags']}")
    print(f"Description: {dev_post_data['article']['description']}")
    print(f"Project ID: {dev_post_data['article']['project_id']}")
    print("--------------------------------------")

if __name__ == "__main__":
    main()
