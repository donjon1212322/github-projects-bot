import json
import os
from jinja2 import Environment, FileSystemLoader

def process_tags(tags):
    processed_tags = []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict):
                tag_name = tag.get("name") or tag.get("slug") or ""
            else:
                tag_name = str(tag)
            processed_tags.append({
                "name": tag_name.strip().lower(),
                "slug": tag_name.strip().lower().replace(' ', '-')
            })
    elif isinstance(tags, str):
        processed_tags = [{
            "name": tag.strip().lower(),
            "slug": tag.strip().lower().replace(' ', '-')
        } for tag in tags.split(',')]

    # Remove duplicates and limit to 5 tags
    return list({tag['name']: tag for tag in processed_tags}.values())[:5]

def generate_slug(title):
    # Replace spaces and invalid characters with hyphens
    slug = title.lower().replace(' ', '-')
    # Remove invalid characters
    slug = ''.join(c for c in slug if c.isalnum() or c == '-')
    # Ensure the slug does not match reserved words and is within length limits
    reserved_words = {"badges", "newsletter", "sponsor", "archive", "members"}
    if slug in reserved_words or not (1 <= len(slug) <= 250):
        slug = f"{slug[:245]}-post"  # Adjust length and ensure uniqueness
    return slug

def format_article_markdown(data):
    env = Environment(loader=FileSystemLoader('data/templates'))
    template = env.get_template('hashnode_template.md')
    tags = process_tags(data['tags'])

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
    hashnode_post_data = {
        "title": article_data["title"],
        "contentMarkdown": formatted_content,
        "tags": process_tags(article_data["tags"]),
        "slug": generate_slug(article_data["title"]),
        "project_id": article_data.get("project_id", ""),
        "coverImage": article_data.get("cover_image", ""),
        "isNewsletterActivated": False,
        "isRepublished": False,
    }
    output_path = os.path.join("data", "hashnode_post.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hashnode_post_data, f, indent=4, ensure_ascii=False)
    print(f"Formatted content saved to {output_path}")
    print("--------------------------------------")
    print("Data being prepared for Hashnode:")
    print(f"Title: {hashnode_post_data['title']}")
    print(f"Content: {hashnode_post_data['contentMarkdown'][:200]}...")
    print(f"Tags: {hashnode_post_data['tags']}")
    print(f"Slug: {hashnode_post_data['slug']}")
    print(f"Project ID: {hashnode_post_data['project_id']}")
    print("--------------------------------------")

if __name__ == "__main__":
    main()
