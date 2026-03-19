"""Google API service initialization."""

from googleapiclient.discovery import build, Resource

from .auth import require_auth


def get_drive_service() -> Resource:
    """Get Google Drive API v3 service."""
    creds = require_auth()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_docs_service() -> Resource:
    """Get Google Docs API v1 service."""
    creds = require_auth()
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def get_sheets_service() -> Resource:
    """Get Google Sheets API v4 service."""
    creds = require_auth()
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_activity_service() -> Resource:
    """Get Google Drive Activity API v2 service."""
    creds = require_auth()
    return build("driveactivity", "v2", credentials=creds, cache_discovery=False)


def get_slides_service() -> Resource:
    """Get Google Slides API v1 service."""
    creds = require_auth()
    return build("slides", "v1", credentials=creds, cache_discovery=False)
