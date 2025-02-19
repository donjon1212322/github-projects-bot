import json
import os
from datetime import datetime

def split_posts():
    """Разделяет посты на части для публикации"""
    try:
        # Загружаем все посты
        with open("data/posts.json", "r", encoding="utf-8") as f:
            posts = json.load(f)
            
        # Загружаем опубликованные посты
        published_ids = set()
        try:
            with open("data/published_posts.json", "r", encoding="utf-8") as f:
                published_ids = set(json.load(f))
        except FileNotFoundError:
            pass
            
        # Фильтруем только новые посты
        new_posts = [post for post in posts if post["project_id"] not in published_ids]
        
        if not new_posts:
            print("No new posts to publish")
            return
            
        # Создаем директорию для очереди если её нет
        os.makedirs("data/queue", exist_ok=True)
        
        # Очищаем старую очередь
        for file in os.listdir("data/queue"):
            if file.endswith(".json"):
                os.remove(os.path.join("data/queue", file))
                
        # Сохраняем каждый пост в отдельный файл
        for i, post in enumerate(new_posts):
            filename = f"data/queue/post_{i:03d}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(post, f, indent=4, ensure_ascii=False)
                
        print(f"Split {len(new_posts)} posts into queue")
        
    except Exception as e:
        print(f"Error splitting posts: {e}")

if __name__ == "__main__":
    split_posts()
