"""Google Drive API operations for listing and downloading ぴよログ export files."""

import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

PIYOLOG_FILENAME_PATTERN = re.compile(r"【ぴよログ】(\d{4})年(\d{1,2})月(\.txt)?$")
PIYOLOG_MIME_TYPE = "text/plain"


@dataclass(frozen=True)
class DriveFile:
    file_id: str
    name: str
    modified_at: datetime


def build_drive_service(credentials: Any) -> Any:
    return build("drive", "v3", credentials=credentials)


def list_piyolog_files(service: Any, folder_id: str) -> list[DriveFile]:
    """List all ぴよログ files in a Drive folder. Handles pagination automatically."""
    results: list[DriveFile] = []
    page_token: str | None = None

    query = (
        f"'{folder_id}' in parents"
        f" and mimeType = '{PIYOLOG_MIME_TYPE}'"
        f" and name contains '【ぴよログ】'"
        f" and trashed = false"
    )

    while True:
        params: dict[str, Any] = {
            "q": query,
            "fields": "nextPageToken, files(id, name, modifiedTime)",
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token

        response = service.files().list(**params).execute(num_retries=3)

        for f in response.get("files", []):
            if PIYOLOG_FILENAME_PATTERN.search(f["name"]):
                modified_at = datetime.fromisoformat(f["modifiedTime"]).astimezone(timezone.utc)
                results.append(DriveFile(file_id=f["id"], name=f["name"], modified_at=modified_at))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def download_file_content(service: Any, file_id: str) -> str:
    """Download a Drive file and return its text content as a UTF-8 string."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk(num_retries=3)
    return buf.getvalue().decode("utf-8")


def parse_year_month_from_filename(file_name: str) -> date:
    """Extract source_year_month (month-first DATE) from filename.

    Raises ValueError if the filename does not match the expected pattern.
    """
    m = PIYOLOG_FILENAME_PATTERN.search(file_name)
    if not m:
        raise ValueError(
            f"Filename does not match 【ぴよログ】YYYY年M月[.txt] pattern: {file_name!r}"
        )
    year = int(m.group(1))
    month = int(m.group(2))
    return date(year, month, 1)
