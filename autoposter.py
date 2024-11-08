import praw
import os
import random
import schedule
import time
import json
import argparse
import subprocess
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
reddit = praw.Reddit(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    user_agent=os.getenv("USER_AGENT"),
    redirect_uri="http://localhost:8000"
)

def authenticate():
    auth_url = reddit.auth.url(
        scopes=['read', 'submit', 'flair', 'modflair', 'vote'], 
        state='unique_state_string', 
        duration='permanent')

    server_process = subprocess.Popen(["python", "-m", "http.server", "8000"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Go to the following URL and authorize the application: {auth_url}")
    code = input("Enter the code from the URL: ")
    reddit.auth.authorize(code)
    print("Authentication successful!")
    server_process.terminate()
    server_process.wait()
    
authenticate()

def load_config(file_path='config.txt'):
    config = {"images": []}
    with open(file_path, 'r') as file:
        lines = file.readlines()

    section = None
    comment_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith("SUBREDDIT="):
            config["subreddit"] = line.split("=", 1)[1]
        elif line.startswith("TITLE="):
            config["title"] = line.split("=", 1)[1]
        elif line.startswith("FLAIR="):
            config["flair"] = line.split("=", 1)[1]
        elif line == "IMAGES":
            section = "images"
        elif section == "images" and line:
            if line == "COMMENT_START":
                section = "comment"
            else:
                config["images"].append(line)
        elif section == "comment" and line != "COMMENT_END":
            comment_lines.append(line)

    config["comment"] = "\n".join(comment_lines).strip()
    return config

def get_image(subfolder_path):
    images = [f for f in os.listdir(subfolder_path) if f.endswith(('.jpg', '.jpeg', '.png'))]
    if images:
        return os.path.join(subfolder_path, random.choice(images))
    return None

def create_post(subreddit_name, title, images, comment_text, flair_text):
    subreddit = reddit.subreddit(subreddit_name)
    image_data = []
    for folder in images:
        subfolder_path = os.path.join('images', folder)
        image_path = get_image(subfolder_path)
        if image_path:
            image_data.append({"image_path": image_path, "caption": folder})
    
    submission = subreddit.submit_gallery(title, image_data)
    
    flair_templates = list(subreddit.flair.link_templates)
    
    flair_template_id = None
    for template in flair_templates:
        if template['text'].lower() == flair_text.lower():
            flair_template_id = template['id']
            break

    if flair_template_id:
        submission.flair.select(flair_template_id)
        print(f"Flair '{flair_text}' applied.")
    else:
        print(f"Flair '{flair_text}' not found. Available flairs: {[t['text'] for t in flair_templates]}")

    print(f"Post Created")

    if comment_text:
        submission.reply(comment_text)
        print("Comment Posted")

    discord_webhook_url = os.getenv("DISCORD_WEBHOOK")
    if discord_webhook_url:
        discord_message = f"https://www.reddit.com{submission.permalink}"
        send_discord_message(discord_webhook_url, discord_message)

def send_discord_message(webhook_url, message):
    data = {
        "content": message
    }
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        print("Posted on Discord")
    else:
        print(f"Discord failure. Status code: {response.status_code}, Response: {response.text}")

def schedule_post():
    print(f"Posting on {datetime.now().strftime('%Y-%m-%d %A %H:%M:%S')}")
    config = load_config()
    create_post(config["subreddit"], config["title"], config["images"], config["comment"], config["flair"])

def main():
    parser = argparse.ArgumentParser(description="Automated Reddit Recruiting Post")
    parser.add_argument('-t', '--test', action='store_true', help="Run a test post.")
    args = parser.parse_args()

    if args.test:
        print("Running a single test post")
        schedule_post()
    else:
        print("Scheduling posts")
        schedule.every().tuesday.at("10:00").do(schedule_post)
        schedule.every().thursday.at("10:00").do(schedule_post)
        schedule.every().saturday.at("10:00").do(schedule_post)

        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    main()