#!/usr/bin/python3
import io
import os
from pathlib import Path

from PIL import Image

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import argparse
import sys
import pandas as pd

host_folder = 'backgrounds'
guest_folder_path = 'autoflows/New'
upload_folder_path = 'autoflows/Done'

SERVICE_ACCOUNT_FILE = './google_disk_credentials/artshyne-f831362c316c.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

def analyze_excel_file(service, file):
    r = download_file(service, file['id'])
    df = pd.read_excel(r, sheet_name='Sheet1')
    result = {}
    for index, row in df.iterrows():
        if pd.notna(row['room']):
            room_name = row['room']
            pic_name = row['pic']
            dict_value = {
                'origin_x': row['origin_x'],
                'origin_y': row['origin_y'],
                'size_w': row['size_w'],
                'size_h': row['size_h']
            }
            pic_dict = {pic_name: dict_value}
            if room_name not in result:
                result[room_name] = [pic_dict]
            else:
                result[room_name].append(pic_dict)
    return result

def main_function(service, folder_name):
    host_folder_id = find_folder_by_name(service, host_folder)
    host_files = list_files(service, host_folder_id)
    for f in host_files:
        if f['name'] == 'origins.xlsx':
            augment_list = analyze_excel_file(service, f)
    print(augment_list)
    host_image_dir_list = augment_list.keys()
    print("Directory", host_image_dir_list)

    host_images = {}
    for f in host_files:
        if f['name'] in host_image_dir_list:
            host_images[f['name']] = download_folder(service, f['id'])
    guest_folder_path_select = guest_folder_path + f"/{folder_name}"
    guest_img_list = get_guest_images(service, guest_folder_path_select)
    print("Guest images are downloaded\n", guest_img_list)

    # Overlay images
    # Create result folder if it doesn't exist
    results = []
    for dir_name in host_image_dir_list:
        host_img_list = augment_list[dir_name]
        for host_img in host_img_list:
            host_img_key = next(iter(host_img.keys()))

            if host_img_key + ".jpg" in host_images[dir_name]:
                host_img_stream = host_images[dir_name][host_img_key + ".jpg"]
                param = host_img[host_img_key]

                for guest_file_name, guest_img_stream in guest_img_list.items():
                    result_stream = io.BytesIO()
                    overlay(host_img_stream, guest_img_stream, result_stream, param)
                    result_file_name = f"{guest_file_name}_{host_img_key}.jpg"
                    results.append((result_file_name, result_stream))

    # Upload result images
    upload_folder_id = find_folder_by_path(service, upload_folder_path)
    for file_name, result_stream in results:
        upload_file(service, upload_folder_id, file_name, result_stream, folder_name)

image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp', 'svg', 'ico', 'heic'}

def get_guest_images(service, guest_folder_path):
    folder_id = find_folder_by_path(service, guest_folder_path)
    folders = list_files(service, folder_id)
    guest_images = {}
    for folder in folders:
        files = list_files(service, folder['id'])
        for file in files:
            if file['name'].split('.')[-1].lower() in image_extensions:
                guest_images[file['name']] = download_file(service, file['id'])
    return guest_images

def find_folder_by_name(service, folder_name, parent_id=None):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])

    if not items:
        print(f"No folder found with the name '{folder_name}'.")
        return None
    elif len(items) > 1:
        print(f'Found {len(items)} folders with the same name, expected to find only one.')
        return None
    else:
        return items[0]['id']

def find_folder_by_path(service, path):
    folders = path.split('/')
    parent_id = None
    for folder in folders:
        folder_id = find_folder_by_name(service, folder, parent_id)
        if not folder_id:
            sys.exit(1)
        parent_id = folder_id
    return parent_id

def list_files(service, folder_id, name=None):
    if not name:
        query = f"'{folder_id}' in parents"
    else:
        query = f"'{folder_id}' in parents and name='{name}'"
    all_items = []
    while True:
        results = service.files().list(q=query,
                                       spaces='drive',
                                       fields='nextPageToken, files(id, name, parents)').execute()
        items = results.get('files', [])
        all_items.extend(items)
        if 'nextPageToken' in results:
            page_token = results['nextPageToken']
        else:
            break
    for f in all_items:
        print(f"{f['name']} -> {f['id']}")
    return all_items

def delete_file(service, file_id):
    try:
        service.files().delete(fileId=file_id).execute()
        print(f"File with ID '{file_id}' deleted successfully.")
    except HttpError as error:
        # print(f"An error occurred: {error}")
        if error.resp.status == 404:
            print("File not found.")
            return False
        elif error.resp.status == 403:
            print("Insufficient permissions to delete the file.")
            return False
    return True

def create_folder(service, parent_folder_id, folder_name):
    # Check if folder already exists
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_folder_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])

    if items:
        print(f"Folder '{folder_name}' already exists with ID {items[0]['id']}")
        return items[0]['id']

    # Create the folder
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id]
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    folder_id = folder.get('id')
    print(f"Created folder '{folder_name}' with ID {folder_id}")
    return folder_id

def upload_file(service, parent_folder_id, file_name, file_stream, new_folder_name=None):
    print(f'Uploading file {file_name}')

    if new_folder_name:
        # Create or find the new folder
        new_folder_id = create_folder(service, parent_folder_id, new_folder_name)
    else:
        new_folder_id = parent_folder_id

    file_metadata = {'name': file_name, 'parents': [new_folder_id]}
    file_stream.seek(0)  # Important: reset stream position to the beginning
    media = MediaIoBaseUpload(file_stream, mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f'Uploaded file ID: {file.get("id")}')
    return True

def download_file(service, file_id):
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")
    file_stream.seek(0)
    return file_stream

def download_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query).execute()
    items = results.get('files', [])
    file_streams = {}
    for item in items:
        file_id = item['id']
        file_name = item['name']
        mime_type = item['mimeType']

        if mime_type == 'application/vnd.google-apps.folder':
            print(f"Skipping subdirectory: {file_name}")
        else:
            print(f"Processing file: {file_name}")
            file_streams[file_name] = download_file(service, file_id)
    return file_streams

def overlay(host_img_stream, guest_img_stream, result_stream, param):
    """
    :param host_img_stream: Byte stream of the background picture
    :param guest_img_stream: Byte stream of the guest picture
    :param result_stream: Byte stream to save the result
    :param param: Dictionary containing origin_x, origin_y, size_w, size_h fields.
    """
    img_background = Image.open(host_img_stream).convert('RGBA')
    img_picture = Image.open(guest_img_stream).convert('RGBA')

    # Resize picture
    new_width = int(param['size_w'])
    new_height = int(param['size_h'])
    img_picture = img_picture.resize((new_width, new_height))

    # calculate the position where the guest image will be placed
    x_offset = int(param['origin_x'] - new_width // 2)
    y_offset = int(param['origin_y'] - new_height // 2)

    img_background.paste(img_picture, (x_offset, y_offset), img_picture)
    result_img = img_background.convert('RGB')
    result_img.save(result_stream, format='JPEG')  # Specify the format explicitly
    print(f'overlay function result prepared')


if __name__ == "__main__":
    service = build('drive', 'v3', credentials=credentials)
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    args = parser.parse_args()
    main_function(service=service, folder_name=args.file)
