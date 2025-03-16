import requests
import os
import json
import logging
from dotenv import load_dotenv
import concurrent.futures

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загружаем переменные окружения из .env файла
load_dotenv()

def upload_image(api_key, image_path, expiration=None):
    try:
        url = "https://api.imgbb.com/1/upload"
        payload = {"key": api_key}
        if expiration:
            payload["expiration"] = str(expiration)
        files = {}
        image_file = open(image_path, "rb")
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        files["image"] = (image_name, image_file)
        response = requests.post(url, data=payload, files=files)
        response.raise_for_status()
        return response.json()
    except FileNotFoundError:
        logging.error(f"Файл не найден: {image_path}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе для {image_path}: {e}")
        return None
    except Exception as e:
        logging.exception(f"Неожиданная ошибка при загрузке {image_path}: {e}")
        return None
    finally:
        if 'image_file' in locals() and image_file:
            image_file.close()

def update_multiple_json_files(project_id, image_url, json_file_paths):
    """Обновляет несколько JSON файлов, добавляя URL изображения"""
    for json_file_path in json_file_paths:
        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            # Проверяем структуру файла и обновляем соответственно
            if json_file_path.endswith('facebook_posts.json'):
                # Существующая логика для facebook_posts.json
                for post in data:
                    if post['project_id'] == project_id:
                        if 'media_urls' not in post:
                            post['media_urls'] = []
                        post['media_urls'].append(image_url)
                        break
            elif json_file_path.endswith('dev_post.json'):
                # Логика для dev_post.json - добавляем media_urls внутрь объекта article
                if 'article' in data and 'project_id' in data['article'] and str(data['article']['project_id']) == str(project_id):
                    if 'media_urls' not in data['article']:
                        data['article']['media_urls'] = []
                    data['article']['media_urls'].append(image_url)
            
            with open(json_file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            
            logging.info(f"Обновлен файл {json_file_path} с URL изображения для проекта {project_id}")
        except Exception as e:
            logging.error(f"Ошибка при обновлении файла {json_file_path}: {e}")

def is_image_file(filename):
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    ext = os.path.splitext(filename)[1].lower()
    return ext in image_extensions

def upload_images_from_directory(api_key, directory_path, json_file_paths, expiration=None):
    """Загружает изображения из директории и обновляет несколько JSON файлов"""
    if not os.path.isdir(directory_path):
        logging.error(f"{directory_path} не является директорией.")
        return
    
    image_files = [os.path.join(directory_path, filename) for filename in os.listdir(directory_path)
                  if os.path.isfile(os.path.join(directory_path, filename)) and is_image_file(os.path.join(directory_path, filename))]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(upload_image, api_key, file_path, expiration): file_path for file_path in image_files}
        for future in concurrent.futures.as_completed(futures):
            file_path = futures[future]
            try:
                result = future.result()
                if result:
                    image_url = result['data']['url']
                    project_id = int(os.path.splitext(os.path.basename(file_path))[0])  # предполагаем, что ID проекта - это имя файла
                    update_multiple_json_files(project_id, image_url, json_file_paths)
                    logging.info(f"Успешно загружено: {os.path.basename(file_path)}. URL: {image_url}")
                else:
                    logging.warning(f"Ошибка при загрузке: {os.path.basename(file_path)}")
            except Exception as e:
                logging.exception(f"Ошибка при обработке результата для {os.path.basename(file_path)}: {e}")

if __name__ == "__main__":
    API_KEY_ibb = os.getenv("API_KEY_ibb")
    if not API_KEY_ibb:
        logging.error("API ключ ImgBB (API_KEY_ibb) не найден в .env файле.")
        exit()
    
    IMAGE_DIRECTORY = "images"  # Замените на путь к вашей директории с изображениями
    JSON_FILE_PATHS = ["data/facebook_posts.json", "data/dev_post.json"]  # Список файлов для обновления
    
    upload_images_from_directory(API_KEY_ibb, IMAGE_DIRECTORY, JSON_FILE_PATHS, expiration=None)
