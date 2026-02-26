"""Google Drive service: authentication, file listing, and downloading."""

import io
import os
import re
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import GDRIVE_SCOPES, SERVICE_ACCOUNT_FILE


def get_service():
    """Get authenticated Google Drive service using local service account file."""
    try:
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=GDRIVE_SCOPES
            )
            service = build("drive", "v3", credentials=credentials)
            return service, None
        return None, "Service account file not found. Add 'service_account.json' to your app folder."
    except Exception as e:
        return None, f"Error connecting to Google Drive: {e}"


@st.cache_data(ttl=600, show_spinner=False)
def list_files_in_folder(_service, folder_id, file_pattern=None):
    """List all Excel files in a Google Drive folder (cached for 10 minutes)."""
    try:
        query = (
            f"'{folder_id}' in parents and "
            "(mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' "
            "or mimeType='application/vnd.ms-excel') and trashed=false"
        )
        results = _service.files().list(
            q=query,
            fields="files(id, name, createdTime, modifiedTime)",
            pageSize=1000,
            orderBy="name",
        ).execute()

        files = results.get("files", [])
        if file_pattern:
            files = [f for f in files if re.search(file_pattern, f["name"])]
        return files
    except Exception as e:
        st.error(f"Error listing files: {e}")
        return []


def download_file(service, file_id):
    """Download a file from Google Drive and return as BytesIO."""
    try:
        request = service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        file_buffer.seek(0)
        return file_buffer
    except Exception as e:
        st.error(f"Error downloading file: {e}")
        return None
