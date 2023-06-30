import io
import os
from typing import List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

cur_dir = os.path.dirname(os.path.realpath(__file__))
svc_accnt_file = os.path.join(cur_dir, 'gdrive-service-account.json')
FUTURE_SIGHT_FOLDER_ID = '18e-93F4AodRZ7zVM_1ye-hPvXFcZux73'


def get_gdrive_service():
    creds = Credentials.from_service_account_file(
        filename=svc_accnt_file,
        scopes=['https://www.googleapis.com/auth/drive.readonly'],
    )
    return build('drive', 'v3', credentials=creds)


def get_file_info(service, file_id):
    file_metadata = (
        service.files().get(fileId=file_id, fields='name, md5Checksum').execute()
    )
    file_name = file_metadata.get('name')
    md5_checksum = file_metadata.get('md5Checksum')
    return file_name, md5_checksum


def list_files_in_gdrive(
    service,
    folder_id: str = FUTURE_SIGHT_FOLDER_ID,
    mime_types: list = [],
    parent_folder_name: str = '',
):
    files = []

    results = (
        service.files()
        .list(
            q="'{}' in parents".format(folder_id),
            pageSize=10,
            fields="nextPageToken, files(id, name, md5Checksum, mimeType, description)",
        )
        .execute()
    )

    items = results.get('files', [])

    if not items:
        return files
    else:
        for item in items:
            if item['mimeType'] == "application/vnd.google-apps.folder":
                # If the item is a folder, add its contents to the list.
                files += list_files_in_gdrive(
                    service,
                    item['id'],
                    mime_types,
                    parent_folder_name + '/' + item['name'],
                )
            elif not mime_types or item['mimeType'] in mime_types:
                # If the item is a file and its MIME type matches, add it to the list.
                files.append(
                    {
                        'name': parent_folder_name + '/' + item['name'],
                        'id': item['id'],
                        'md5': item['md5Checksum'],
                        'description': item['description'],
                    }
                )

    return files


def download_file(service, file_id, output_file):
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(output_file, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print("Download %d%%." % int(status.progress() * 100))
