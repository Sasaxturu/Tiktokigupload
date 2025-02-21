import requests
import os
import json
import time
import re
import telebot
import threading
import subprocess

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1337851716"))
ALLOWED_USERS = list(map(int, os.getenv("ALLOWED_USERS", "1337851716,1164505656").split(',')))

bot = telebot.TeleBot(TOKEN)

INSTAGRAM_API_URL = "https://itzpire.com/download/instagram"
TIKTOK_API_URL = "https://www.laurine.site/api/downloader/tiktok"

queue = []

def send_error_log(error_message):
    try:
        bot.send_message(ADMIN_ID, f"Error Log: {error_message}")
    except Exception as e:
        print(f"Gagal mengirim log error: {e}")

def download_file(url, file_path):
    try:
        response = requests.get(url, stream=True, timeout=200)
        if response.status_code == 200:
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        return False
    except Exception as e:
        send_error_log(f"Error download file: {e}")
        return False

def fetch_instagram_data(url):
    try:
        full_api_url = f"{INSTAGRAM_API_URL}?url={url}"
        result = subprocess.run(["curl", "-X", "GET", full_api_url, "-H", "Accept: application/json"],
                                capture_output=True, text=True, timeout=200)
        if result.returncode != 0:
            send_error_log("Terjadi kesalahan saat mengakses API Instagram.")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        send_error_log(f"Error fetching Instagram data: {e}")
        return None

def fetch_tiktok_data(url):
    try:
        response = requests.get(f"{TIKTOK_API_URL}?url={url}", headers={"accept": "*/*"}, timeout=200)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        send_error_log(f"Error fetching TikTok data: {e}")
        return None

def upload_to_channel(url, caption, is_tiktok):
    try:
        data = fetch_tiktok_data(url) if is_tiktok else fetch_instagram_data(url)
        if not data or "data" not in data:
            send_error_log("Gagal mengambil data. Pastikan link valid.")
            return "Gagal mengambil data. Pastikan link valid."

        media_list = []
        if is_tiktok:
            video_url = data["data"].get("no_watermark") or data["data"].get("watermark")
            if video_url:
                media_list.append({"type": "video", "url": video_url})
        else:
            media_list = data["data"].get("media", [])

        media_group = []
        for index, media in enumerate(media_list, start=1):
            media_url = media.get("downloadUrl", media.get("url"))
            file_path = f"media_{index}.{'mp4' if media.get('type') == 'video' else 'jpg'}"

            if download_file(media_url, file_path):
                with open(file_path, "rb") as file:
                    if media.get("type") == "video":
                        media_group.append(telebot.types.InputMediaVideo(file.read(), caption=caption if index == 1 else ""))
                    else:
                        media_group.append(telebot.types.InputMediaPhoto(file.read(), caption=caption if index == 1 else ""))
                os.remove(file_path)
            else:
                send_error_log(f"Gagal mengunduh media {index}.")
                return f"Gagal mengunduh media {index}. Coba lagi nanti."

        if len(media_group) > 1:
            bot.send_media_group(CHANNEL_ID, media_group)
        elif len(media_group) == 1:
            if isinstance(media_group[0], telebot.types.InputMediaVideo):
                bot.send_video(CHANNEL_ID, media_group[0].media, caption=caption)
            else:
                bot.send_photo(CHANNEL_ID, media_group[0].media, caption=caption)
        
        return "Sukses"
    except Exception as e:
        send_error_log(f"Error: {e}")
        return f"Error: {e}"

@bot.message_handler(func=lambda message: message.from_user.id in ALLOWED_USERS and ('instagram.com' in message.text or 'tiktok.com' in message.text))
def handle_social_links(message):
    global queue
    try:
        pattern = r"\s*,\s*|\s+,"
        parts = re.split(pattern, message.text.strip())
        urls_and_captions = [(parts[i].strip(), parts[i + 1].strip() if i + 1 < len(parts) else "Media dari bot")
                             for i in range(0, len(parts), 2)]
        for url, caption in urls_and_captions:
            is_tiktok = "tiktok.com" in url
            queue.append((url.split('?')[0], caption, is_tiktok))
            bot.send_message(message.chat.id, "Pesan ditambahkan ke antrian. Akan diproses dalam 15 menit.")
    except Exception as e:
        send_error_log(f"Error: {e}")
        bot.send_message(message.chat.id, f"Error: {e}")

def process_queue():
    global queue
    while True:
        if queue:
            url, caption, is_tiktok = queue.pop(0)
            upload_to_channel(url, caption, is_tiktok)
            time.sleep(420)
        else:
            time.sleep(10)

threading.Thread(target=process_queue, daemon=True).start()
bot.polling()
                              
