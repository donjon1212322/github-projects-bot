import json
import os
from dotenv import load_dotenv
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения из .env
load_dotenv()

# Конфигурация Google Sheets
SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")
RANGE_NAME = 'Sheet1'

def main():
    """Записывает данные из facebook_posts.json в Google Таблицы."""
    try:
        # Аутентификация
        creds = service_account.Credentials.from_service_account_info(
            json.loads(GOOGLE_CREDENTIALS), scopes=['https://www.googleapis.com/auth/spreadsheets'])

        # Создание сервиса Google Sheets API
        service = build('sheets', 'v4', credentials=creds)

        # Проверка существования таблицы
        try:
            spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
            logging.info(f"Таблица '{spreadsheet.get('properties').get('title')}' найдена.")
        except HttpError as e:
            logging.error(f"Ошибка при получении информации о таблице: {e}")
            return  # Завершить выполнение, если таблица не найдена

        # Чтение данных из facebook_posts.json
        with open("data/facebook_posts.json", "r", encoding="utf-8") as f:
            posts = json.load(f)

        # Определение заголовков столбцов
        headers = ["project_id", "content", "platform", "media_urls"]

        # Проверка наличия заголовков в Google Таблице
        try:
            range_to_check = f"{RANGE_NAME}!A1:D1"  # Проверяем первые 4 ячейки
            result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_to_check).execute()
            values = result.get('values', [])
            if not values:
                # Заголовков нет, создаем их
                body = {
                    'values': [headers]  # Отправляем список заголовков как первую строку
                }
                result = service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID, range=range_to_check,
                    valueInputOption="USER_ENTERED", body=body).execute()
                logging.info("Заголовки созданы.")
            else:
                logging.info("Заголовки уже существуют.")
        except HttpError as e:
            logging.error(f"Ошибка при проверке или создании заголовков: {e}")
            return  # Завершить выполнение, если произошла ошибка

        # Подготовка данных для записи в таблицу
        values = []
        for post in posts:
            row = [
                post["project_id"],
                post["content"],
                post["platform"],
                post["media_urls"][1] if len(post["media_urls"]) > 1 else post["media_urls"][0] if post["media_urls"] else ""
            ]
            values.append(row)

        # Запись данных в Google Таблицы (добавление в конец)
        body = {
            'values': values
        }
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
            valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
            body=body).execute()
        logging.info(f"{result.get('updates').get('updatedCells')} ячеек добавлено.")
    except HttpError as err:
        logging.error(err)
    except ValueError as err:
        logging.error(err)
    except Exception as err:
        logging.error(f"An unexpected error occurred: {err}")

if __name__ == '__main__':
    main()
