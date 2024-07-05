#!/usr/bin/python3
import io
import os
from pathlib import Path

from PIL import Image

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
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
    r = download_file(service, file['id'], file['name'], host_folder)
    df = pd.read_excel(f"{host_folder}/{file['name']}", sheet_name='Sheet1')
    list_of_dicts = []
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

def get_full_file_name(directory, base_name):
    # Iterate through all files in the directory
    for file in os.listdir(directory):
        # Check if the file name (without extension) matches the base name
        if Path(file).stem == base_name:
            return file
    return None

def main_function(service, folder_name):
    host_folder_id = find_folder_by_name(service, host_folder)
    host_files = list_files(service, host_folder_id)
    for f in host_files:
        if f['name'] == 'origins.xlsx':
            augment_list = analyze_excel_file(service, f)
    print(augment_list)
    host_image_dir_list = augment_list.keys()
    print("Directory", host_image_dir_list)
    for f in host_files:
        if f['name'] in host_image_dir_list:
            r = download_folder(service, f['id'], os.path.join(host_folder, f['name']))
            if r is not True:
                continue
    guest_folder_path_select = guest_folder_path + f"/{folder_name}"
    guest_img_list = get_guest_images(service, guest_folder_path_select)
    print("Guest images are downloaded\n", guest_img_list)

    # Overlay images
    # Create result folder if it doesn't exist
    result_folder_path = 'Done'
    result_folder_path = Path(result_folder_path)
    result_folder_path.mkdir(parents=True, exist_ok=True)
    for dir in host_image_dir_list:
        host_img_list = augment_list[dir]
        for host_img in host_img_list:
            host_img_key = next(iter(host_img.keys()))
            # Find the full file name within the directory
            dir_path = Path(host_folder) / dir
            full_file_name = get_full_file_name(dir_path, host_img_key)
            
            if full_file_name:
                host_path = dir_path / full_file_name
                param = host_img[host_img_key]

                for guest_img in guest_img_list:
                    guest_path = Path("guest_img") / guest_img['name']
                    result_path = result_folder_path / f"{guest_img['name']}_{full_file_name}"
                    overlay(host_path, guest_path, result_path, param)
            else:
                print(f"File with base name {host_img_key} not found in {dir_path}")
    
    # Upload result images
    upload_folder_id = find_folder_by_path(service, upload_folder_path + f'/{folder_name}')
    result_folder_path = Path('Done')
    for file in os.listdir(Path('Done')):
        result_file = result_folder_path / Path(file)
        upload_file(service, upload_folder_id, result_file, delete=True)

# def main_function1(service):
#     host_folder_id = find_folder_by_name(service, host_folder)
#     host_files = list_files(service, host_folder_id)
#     for f in host_files:
#         if f['name'] == 'origins.xlsx':
#             augment_list = analyze_excel_file(service, f)
#     print(augment_list)
#     host_image_dir_list = augment_list.keys()
#     print("Directory", host_image_dir_list)
#     for folder in host_files:
#         if folder['name'] in host_image_dir_list:
#             host_img_files = list_files(service, folder['id'])
#             for host_img in host_img_files:
                
#             r = download_folder(service, f['id'], os.path.join(host_folder, f['name']))
#             if r is not True:
#                 continue
            
#     guest_img_list = get_guest_images(service)
#     print("Guest images are downloaded\n", guest_img_list)

#     # Overlay images
#     # Create result folder if it doesn't exist
#     result_folder_path = 'Done'
#     result_folder_path = Path(result_folder_path)
#     result_folder_path.mkdir(parents=True, exist_ok=True)
#     for dir in host_image_dir_list:
#         host_img_list = augment_list[dir]
#         for host_img in host_img_list:
#             host_img_key = next(iter(host_img.keys()))
#             # Find the full file name within the directory
#             dir_path = Path(host_folder) / dir
#             full_file_name = get_full_file_name(dir_path, host_img_key)
            
#             if full_file_name:
#                 host_path = dir_path / full_file_name
#                 param = host_img[host_img_key]

#                 for guest_img in guest_img_list:
#                     guest_path = Path("guest_img") / guest_img['name']
#                     result_path = result_folder_path / f"{guest_img['name']}_{full_file_name}"
#                     overlay(host_path, guest_path, result_path, param)
#             else:
#                 print(f"File with base name {host_img_key} not found in {dir_path}")
    
#     # Upload result images
#     upload_folder_id = find_folder_by_path(service, upload_folder_path)
#     result_folder_path = Path('Done')
#     for file in os.listdir(Path('Done')):
#         result_file = result_folder_path / Path(file)
#         upload_file(service, upload_folder_id, result_file, delete=True)

    
    
image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp', 'svg', 'ico', 'heic'}

def get_guest_images(service):
    folder_id = find_folder_by_path(service, guest_folder_path)
    files = list_files(service, folder_id)
    guest_image_lists = []
    for file in files:
        if file['name'].split('.')[-1].lower() in image_extensions:
            guest_image_lists.append(file)
            r = download_file(service=service, file_id=file['id'],  file_name=file['name'], destination_path='guest_img')
    return guest_image_lists

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
        # print(f"Found folder {folder_name} -> {items[0]['id']}")
        return items[0]['id']
        # print(f"Found folder(s):")
        # for item in items:
        #     print(f"{item['name']} ({item['id']})")

    # return items

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

def upload_file(service, folder_id, fpath, delete=False):
    print(f'Uploading file {fpath}')
    fname = Path(fpath).name
    file_path = Path(fpath).parent

    # check for files with the same name
    same_names = list_files(service, folder_id, name=fname)
    if len(same_names) != 0:
        if delete:
            print(f'File with name {fname} already exists, delete...')
            if len(same_names) != 1:
                print(f'Too many files {fname}: {len(same_names)} expected: 1')
                return False
            r = delete_file(service, same_names[0]['id'])
            if r is not True:
                return False
        else:
            print(f'File {fname} already exists, cannot upload.')
            return False

    file_metadata = {'name': str(fname), 'parents': [folder_id]}
    media = MediaFileUpload(fpath, mimetype='application/octet-stream')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f'Uploaded file ID: {file.get("id")}')


    # file_path = 'path/to/your/local/file'
    # upload_file(service, file_metadata, file_path)
    return True

def download_file(service, file_id, file_name, destination_path):
    """Ensure that a directory exists."""
    if not os.path.exists(destination_path):
        os.makedirs(destination_path)
    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join(destination_path, file_name)
    with open(file_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {file_name}: {int(status.progress() * 100)}%")

def download_folder(service, folder_id, destination_path = host_folder):
    # Ensure destination path exists
    if not os.path.exists(destination_path):
        os.makedirs(destination_path)

    # List files and subdirectories in the specified directory
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query).execute()
    items = results.get('files', [])

    if not items:
        print(f"No files found in directory {folder_id}.")
        return False

    for item in items:
        file_id = item['id']
        file_name = item['name']
        mime_type = item['mimeType']

        if mime_type == 'application/vnd.google-apps.folder':  # It's a subdirectory
            print(f"Found subdirectory: {file_name}")
            new_destination_path = os.path.join(destination_path, file_name)
            download_folder(service, file_id, new_destination_path)
        else:  # It's a file
            print(f"Found file: {file_name}")
            download_file(service, file_id, file_name, destination_path)
    return True

def overlay(host_img, guest_img, result_path, param):
    """

    :param host_img: backgroud picture
    :param guest_img:
    :param result_path: where to save the results
    :param center: where to place the picture. (0.5, 0.5) corresponds to the center of the picture
    :param guest_scaling: how to scale the picture
    :return:
    """
    img_background = Image.open(host_img)
    img_picture = Image.open(guest_img)

    # Resize picture
    new_width = int(param['size_w'])
    new_height = int(param['size_h'])
    img_picture = img_picture.resize((new_width, new_height))

    #center coordinates
    cx, cy = param['origin_x'], param['origin_y']

    # left upper corner
    # x_offset = (img_background.width - img_picture.width) // 2
    # y_offset = (img_background.height - img_picture.height) // 2
    x_offset = int(cx - img_picture.width // 2)
    y_offset = int(cy - img_picture.height // 2)

    img_background.paste(img_picture, (x_offset, y_offset))
    img_background.save(result_path)
    print(f'overlay function result saved to: {result_path}')


if __name__ == "__main__":
    # Define a custom argument type for a list of strings
    def list_of_strings(arg):
        return arg.split(',')

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser')

    parser_list = subparsers.add_parser('list')
    
    parser_main = subparsers.add_parser('main')
    parser_main.add_argument('file')
    # parser_list.add_argument(''

    parser_delete = subparsers.add_parser('delete')
    parser_delete.add_argument('file_id', help='file id to be deleted')

    parser_download = subparsers.add_parser('download')
    parser_download.add_argument('file')


    parser_upload = subparsers.add_parser('upload')
    parser_upload.add_argument('file')

    parser_overlay = subparsers.add_parser('overlay')
    parser_overlay.add_argument('host_img', help="host image")
    parser_overlay.add_argument('guest_img', help='guest image')
    parser_overlay.add_argument('-c', type=list_of_strings, help="center")
    parser_overlay.add_argument('-s', help="scale")

    parser_excel = subparsers.add_parser('excel')
    parser_excel.add_argument('file')

    args = parser.parse_args()
    # print(args)
    service = build('drive', 'v3', credentials=credentials)

    if args.subparser == 'list':
        # folder_id = find_folder_by_path(service, guest_folder_path)
        folder_id = find_folder_by_name(service, host_folder)
        files = list_files(service, folder_id)
        print(f'Directory {guest_folder_path} -> {folder_id} content:{os.linesep}')
        for f in files:
            print(f"{f['name']} -> {f['id']}")
    elif args.subparser == 'delete':
        # folder_id = find_folder_by_name(service, root_folder)
        delete_file(service, args.file_id)
    elif args.subparser == 'upload':
        folder_id = find_folder_by_path(service, guest_folder_path)
        upload_file(service, folder_id, args.file)
    elif args.subparser == 'download':
        folder_id = find_folder_by_path(service, guest_folder_path)
        r = download_file(service, folder_id, args.file)
        if not r:
            print(f'failed to download the file')
            sys.exit(1)
    elif args.subparser == 'overlay':
        # overlay Designer.jpeg 10373.jpg (0.5, 0.5) 0.1
        # overlay Designer.jpeg 10373.jpg -c 0.5,0.5 -s 0.1
        host_img_name = args.host_img
        guest_img_name = args.guest_img
        host_path = Path(host_folder) / host_img_name
        guest_path = Path(host_folder) / guest_img_name
        center = args.c
        scale = args.s
        # download both files
        folder_id = find_folder_by_name(service, host_folder)
        r = download_file(service, folder_id, host_path.name)
        if r is not True:
            sys.exit(1)
        r = download_file(service, folder_id, guest_path.name)
        if r is not True:
            sys.exit(1)
        result_path = host_path.parent / f'final_{host_path.stem}{host_path.suffix}'
        overlay(host_path, guest_path, result_path, center, guest_scaling=scale)
        upload_file(service, folder_id, result_path, delete=True)

    elif args.subparser == 'main':
        main_function(service=service, folder_name=args.file)
#     if args.sdfsdf:
#        pass
    # save final_
