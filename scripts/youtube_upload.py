#!/usr/bin/env python3
"""
YouTube video uploader for bilingual audiobook projects.

Requires:
1. Google Cloud project with YouTube Data API v3 enabled
2. OAuth 2.0 Client ID (Desktop app) - download as client_secrets.json
3. pip install google-auth google-auth-oauthlib google-api-python-client

Usage:
    python scripts/youtube_upload.py "Project Name"
    python scripts/youtube_upload.py "Абсолютное оружие_ru_es-latam"
    python scripts/youtube_upload.py "Абсолютное оружие_ru_es-latam" --privacy public
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)

from project.manager import ProjectManager

# OAuth scopes
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",  # For thumbnail updates
]

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SECRETS_PATH = PROJECT_ROOT / "client_secrets.json"
TOKEN_PATH = PROJECT_ROOT / ".youtube_token.json"


# Language display names
LANG_NAMES = {
    "ru": "Russian",
    "en": "English",
    "es": "Spanish",
    "es-latam": "Latin American Spanish",
    "es-ar": "Argentine Spanish",
    "de": "German",
    "fr": "French",
    "pt-br": "Brazilian Portuguese",
}

# Hashtags by target language
LANG_HASHTAGS = {
    "es": "#LearnSpanish #Bilingual #LanguageLearning #español",
    "es-latam": "#LearnSpanish #Bilingual #LanguageLearning #испанский",
    "es-ar": "#LearnSpanish #Bilingual #LanguageLearning #испанский",
    "en": "#LearnEnglish #Bilingual #LanguageLearning #английский",
    "de": "#LearnGerman #Bilingual #LanguageLearning #немецкий",
    "fr": "#LearnFrench #Bilingual #LanguageLearning #французский",
    "pt-br": "#LearnPortuguese #Bilingual #LanguageLearning #португальский",
}

# Tags by target language (no # symbols)
LANG_TAGS = {
    "es": "learn Spanish, Spanish for Russians, bilingual, language learning, passive learning, español, испанский язык, учу испанский, Russian Spanish, изучение языков",
    "es-latam": "learn Spanish, Spanish for Russians, bilingual, language learning, passive learning, español latino, испанский язык, учу испанский, español argentino, Russian Spanish, изучение языков",
    "es-ar": "learn Spanish, Spanish for Russians, bilingual, language learning, passive learning, español latino, испанский язык, учу испанский, español argentino, Russian Spanish, изучение языков",
    "en": "learn English, English for Russians, bilingual, language learning, passive learning, английский язык, учу английский, Russian English, изучение языков",
}


def get_authenticated_service():
    """Get authenticated YouTube API service."""
    creds = None

    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            if not SECRETS_PATH.exists():
                print(f"ERROR: {SECRETS_PATH} not found!")
                print("\nTo set up YouTube API:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project (or use existing)")
                print("3. Enable 'YouTube Data API v3'")
                print("4. Create OAuth 2.0 Client ID (Desktop app)")
                print(f"5. Download and save as: {SECRETS_PATH}")
                sys.exit(1)

            print("Opening browser for authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token
        TOKEN_PATH.write_text(creds.to_json())
        print(f"Token saved to {TOKEN_PATH}")

    return build("youtube", "v3", credentials=creds)


def generate_metadata(project_name: str, source_lang: str, target_lang: str) -> dict:
    """Generate YouTube metadata from project info."""

    # Extract work name from project name (remove lang suffixes)
    work_name = project_name
    for suffix in [f"_{source_lang}_{target_lang}", f"_{source_lang}", f"_{target_lang}"]:
        if work_name.endswith(suffix):
            work_name = work_name[:-len(suffix)]

    # Language codes for title
    src_code = source_lang.upper()
    tgt_code = target_lang.upper().replace("-", " ")

    # Get language names
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)

    # Title
    title = f"[Bilingual][{src_code}→{tgt_code}] {work_name}"

    # Description
    hashtags = LANG_HASHTAGS.get(target_lang, "#Bilingual #LanguageLearning")
    description = f"""🎧 AI-generated bilingual audio for passive language learning.
Each sentence: first {src_name}, then {tgt_name}.

⚠️ Neural TTS - minor errors possible. Premium voices coming soon.

📩 Want other languages or texts? Drop a comment!

{hashtags}"""

    # Tags
    base_tags = LANG_TAGS.get(target_lang, "bilingual, language learning")
    tags = [t.strip() for t in base_tags.split(",")]

    # Add work-specific tags
    tags.append(work_name)

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category": "27",  # Education
    }


def upload_video(
    youtube,
    video_path: Path,
    title: str,
    description: str,
    tags: list,
    category: str = "27",
    privacy: str = "private",
    playlist_id: Optional[str] = None,
    publish_at: Optional[datetime] = None,
) -> dict:
    """Upload video to YouTube.

    Args:
        publish_at: Schedule video publication (UTC datetime).
                    If provided, video will be private until this time.
    """

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "private" if publish_at else privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Schedule publication if publish_at is provided
    if publish_at:
        # Convert to ISO 8601 format with Z suffix (UTC)
        body["status"]["publishAt"] = publish_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 10,  # 10MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    print("\nUploading...")

    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"  {progress}% uploaded", end="\r")

    print(f"\n✅ Upload complete!")
    print(f"   Video ID: {response['id']}")
    print(f"   URL: https://youtu.be/{response['id']}")

    # Add to playlist if specified
    if playlist_id and response.get("id"):
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": response["id"],
                        },
                    }
                },
            ).execute()
            print(f"   Added to playlist: {playlist_id}")
        except Exception as e:
            print(f"   Warning: Failed to add to playlist: {e}")

    return response


def update_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> dict:
    """Update thumbnail for an existing YouTube video.

    Args:
        youtube: Authenticated YouTube API service
        video_id: YouTube video ID
        thumbnail_path: Path to thumbnail image (JPEG, PNG, GIF, BMP - max 2MB)

    Returns:
        API response
    """
    if not thumbnail_path.exists():
        raise FileNotFoundError(f"Thumbnail not found: {thumbnail_path}")

    # Check file size (max 2MB)
    file_size = thumbnail_path.stat().st_size
    if file_size > 2 * 1024 * 1024:
        raise ValueError(f"Thumbnail too large: {file_size / (1024*1024):.1f}MB (max 2MB)")

    # Determine mime type
    suffix = thumbnail_path.suffix.lower()
    mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                  ".gif": "image/gif", ".bmp": "image/bmp"}
    mime_type = mime_types.get(suffix, "image/png")

    media = MediaFileUpload(str(thumbnail_path), mimetype=mime_type)

    response = youtube.thumbnails().set(
        videoId=video_id,
        media_body=media
    ).execute()

    print(f"✅ Thumbnail updated for video {video_id}")
    return response


def cmd_update_thumbnail(args):
    """Command to update thumbnail for a video."""
    youtube = get_authenticated_service()

    # Find video ID - either direct or from project
    video_id = args.video_id

    # Find thumbnail path
    thumbnail_path = Path(args.thumbnail)
    if not thumbnail_path.exists():
        print(f"ERROR: Thumbnail not found: {thumbnail_path}")
        sys.exit(1)

    print(f"Updating thumbnail for video: {video_id}")
    print(f"Thumbnail: {thumbnail_path}")

    if not args.yes:
        confirm = input("Proceed? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return

    result = update_thumbnail(youtube, video_id, thumbnail_path)
    print(f"Done! New thumbnail URL: {result.get('items', [{}])[0].get('default', {}).get('url', 'N/A')}")


def cmd_update_all_thumbnails(args):
    """Update thumbnails for all videos in books_posted table.

    Uses pre-generated thumbnails from thumbnails/ folder.
    Thumbnails are named by book_key (e.g., asimov_profession.png).
    """
    import sqlite3

    youtube = get_authenticated_service()
    db_path = PROJECT_ROOT / "general.db"
    thumbnails_dir = PROJECT_ROOT / "thumbnails"

    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        sys.exit(1)

    if not thumbnails_dir.exists():
        print(f"ERROR: Thumbnails directory not found: {thumbnails_dir}")
        print("Run: python scripts/generate_thumbnails.py")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("""
        SELECT youtube_id, project_name, author, title, source_lang, target_lang
        FROM books_posted
        WHERE youtube_id IS NOT NULL
    """)
    videos = cursor.fetchall()
    conn.close()

    if not videos:
        print("No videos found in books_posted table")
        return

    print(f"Found {len(videos)} videos to update:\n")
    for video_id, project_name, author, title, src_lang, tgt_lang in videos:
        # Extract book key from project_name (e.g., asimov_profession_ru_es-latam -> asimov_profession)
        parts = project_name.rsplit("_", 2)
        book_key = parts[0] if len(parts) >= 3 else project_name
        thumb_path = thumbnails_dir / f"{book_key}.png"
        status = "✓" if thumb_path.exists() else "✗"
        print(f"  {status} {video_id}: {author} - {title} ({book_key}.png)")

    if not args.yes:
        confirm = input(f"\nUpdate thumbnails for all {len(videos)} videos? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return

    success = 0
    for video_id, project_name, author, title, src_lang, tgt_lang in videos:
        print(f"\n{'='*60}")
        print(f"Processing: {author} - {title}")

        # Extract book key from project_name
        parts = project_name.rsplit("_", 2)
        book_key = parts[0] if len(parts) >= 3 else project_name

        # Find thumbnail in thumbnails/ folder
        thumb_path = thumbnails_dir / f"{book_key}.png"
        if not thumb_path.exists():
            print(f"  ❌ Thumbnail not found: {thumb_path}")
            continue

        # Upload to YouTube
        try:
            update_thumbnail(youtube, video_id, thumb_path)
            success += 1
        except Exception as e:
            print(f"  ❌ ERROR uploading thumbnail: {e}")

    print(f"\n{'='*60}")
    print(f"Done! Updated {success}/{len(videos)} thumbnails")


def parse_schedule_time(value: str) -> datetime:
    """Parse schedule time string.

    Supports:
      - 'tomorrow' or 'tomorrow 14:00' - tomorrow at specified time (default 12:00)
      - 'HH:MM' - today at specified time (if in future) or tomorrow
      - '+Nh' or '+Nm' - relative time (hours/minutes from now)
      - ISO format: '2024-12-10T14:00:00'
    """
    now = datetime.now(timezone.utc)
    local_tz = datetime.now().astimezone().tzinfo

    value = value.strip().lower()

    # Tomorrow shortcut
    if value.startswith("tomorrow"):
        parts = value.split()
        if len(parts) > 1:
            time_str = parts[1]
            hour, minute = map(int, time_str.split(":"))
        else:
            hour, minute = 12, 0  # Default to noon

        tomorrow = datetime.now(local_tz) + timedelta(days=1)
        scheduled = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return scheduled.astimezone(timezone.utc)

    # Relative time (+2h, +30m)
    if value.startswith("+"):
        if value.endswith("h"):
            hours = int(value[1:-1])
            return now + timedelta(hours=hours)
        elif value.endswith("m"):
            minutes = int(value[1:-1])
            return now + timedelta(minutes=minutes)

    # Time only (HH:MM)
    if ":" in value and len(value) <= 5:
        hour, minute = map(int, value.split(":"))
        scheduled = datetime.now(local_tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
        # If time already passed today, schedule for tomorrow
        if scheduled <= datetime.now(local_tz):
            scheduled += timedelta(days=1)
        return scheduled.astimezone(timezone.utc)

    # ISO format
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local_tz)
        return dt.astimezone(timezone.utc)
    except ValueError:
        raise ValueError(f"Cannot parse schedule time: {value}")


def main():
    parser = argparse.ArgumentParser(description="Upload bilingual audiobook to YouTube")
    subparsers = parser.add_subparsers(dest="command")

    # Upload command (default behavior when no subcommand)
    upload_parser = subparsers.add_parser("upload", help="Upload video to YouTube")
    upload_parser.add_argument("project", help="Project name or path")
    upload_parser.add_argument("thumbnail", help="Path to thumbnail image (required)")
    upload_parser.add_argument("--privacy", choices=["private", "unlisted", "public"],
                               default="public", help="Video privacy status")
    upload_parser.add_argument("--schedule", metavar="TIME",
                               help="Schedule publication: 'tomorrow', 'tomorrow 14:00', '18:00', '+2h', or ISO datetime")
    upload_parser.add_argument("--playlist", help="Playlist ID to add video to")
    upload_parser.add_argument("--title", help="Override generated title")
    upload_parser.add_argument("--dry-run", action="store_true", help="Show metadata without uploading")
    upload_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # Update thumbnail command
    thumb_parser = subparsers.add_parser("thumbnail", help="Update thumbnail for a video")
    thumb_parser.add_argument("video_id", help="YouTube video ID")
    thumb_parser.add_argument("thumbnail", help="Path to thumbnail image")
    thumb_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # Update all thumbnails command
    all_thumbs_parser = subparsers.add_parser("update-all-thumbnails",
                                               help="Generate and update thumbnails for all videos in books_posted")
    all_thumbs_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    parser.add_argument("--privacy", choices=["private", "unlisted", "public"],
                       default="public", help="Video privacy status")
    parser.add_argument("--schedule", metavar="TIME",
                       help="Schedule publication: 'tomorrow', 'tomorrow 14:00', '18:00', '+2h', or ISO datetime")
    parser.add_argument("--playlist", help="Playlist ID to add video to")
    parser.add_argument("--title", help="Override generated title")
    parser.add_argument("--dry-run", action="store_true", help="Show metadata without uploading")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    # Route to appropriate command
    if args.command == "thumbnail":
        cmd_update_thumbnail(args)
        return
    elif args.command == "update-all-thumbnails":
        cmd_update_all_thumbnails(args)
        return
    elif args.command == "upload":
        # Use upload subparser args
        pass
    else:
        parser.print_help()
        return

    # Parse schedule time if provided
    publish_at = None
    if args.schedule:
        try:
            publish_at = parse_schedule_time(args.schedule)
        except ValueError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    # Find project
    manager = ProjectManager(PROJECT_ROOT / "projects")
    project = manager.get_project(args.project)

    if not project:
        print(f"ERROR: Project '{args.project}' not found")
        print("\nAvailable projects:")
        for name in manager.list_projects():
            print(f"  - {name}")
        sys.exit(1)

    # Check video exists
    video_path = project.get_output_video_path()
    if not video_path.exists():
        print(f"ERROR: Video not found: {video_path}")
        print("Run the pipeline first to generate the video.")
        sys.exit(1)

    # Check thumbnail exists
    thumbnail_path = Path(args.thumbnail)
    if not thumbnail_path.exists():
        print(f"ERROR: Thumbnail not found: {thumbnail_path}")
        sys.exit(1)

    # Check thumbnail size (max 2MB)
    thumb_size = thumbnail_path.stat().st_size
    if thumb_size > 2 * 1024 * 1024:
        print(f"ERROR: Thumbnail too large: {thumb_size / (1024*1024):.1f}MB (max 2MB)")
        sys.exit(1)

    # Get video file size
    video_size_mb = video_path.stat().st_size / (1024 * 1024)

    # Generate metadata
    meta = generate_metadata(
        project.dir.name,
        project.meta.source_lang,
        project.meta.target_lang,
    )

    # Override title if provided
    if args.title:
        meta["title"] = args.title

    # Display all info
    print("=" * 60)
    print("YOUTUBE UPLOAD PREVIEW")
    print("=" * 60)
    print()
    print(f"📁 Project: {project.dir.name}")
    print(f"🎬 Video: {video_path}")
    print(f"📦 Size: {video_size_mb:.1f} MB")
    print(f"🖼️  Thumbnail: {thumbnail_path}")
    if publish_at:
        local_time = publish_at.astimezone(datetime.now().astimezone().tzinfo)
        print(f"📅 Scheduled: {local_time.strftime('%Y-%m-%d %H:%M')} (local)")
        print(f"            {publish_at.strftime('%Y-%m-%dT%H:%M:%SZ')} (UTC)")
    else:
        print(f"🔒 Privacy: {args.privacy}")
    print()
    print("-" * 60)
    print("TITLE:")
    print("-" * 60)
    print(meta["title"])
    print()
    print("-" * 60)
    print("DESCRIPTION:")
    print("-" * 60)
    print(meta["description"])
    print()
    print("-" * 60)
    print("TAGS:")
    print("-" * 60)
    print(", ".join(meta["tags"]))
    print()
    print("-" * 60)
    print(f"CATEGORY: {meta['category']} (Education)")
    if args.playlist:
        print(f"PLAYLIST: {args.playlist}")
    print("=" * 60)

    # Authenticate first to show channel info
    print("\nAuthenticating...")
    youtube = get_authenticated_service()

    # Get and display channel info
    channel_response = youtube.channels().list(part="snippet", mine=True).execute()
    if not channel_response.get("items"):
        print("ERROR: No YouTube channel found for this account!")
        sys.exit(1)

    channel = channel_response["items"][0]
    channel_name = channel["snippet"]["title"]
    channel_id = channel["id"]

    print()
    print("=" * 60)
    print(f"📺 CHANNEL: {channel_name}")
    print(f"   https://youtube.com/channel/{channel_id}")
    print("=" * 60)

    # Get playlists if user wants to select one
    if not args.playlist:
        print("\n📋 Your playlists:")
        playlists_response = youtube.playlists().list(
            part="snippet", mine=True, maxResults=25
        ).execute()
        playlists = playlists_response.get("items", [])

        if playlists:
            for i, pl in enumerate(playlists, 1):
                print(f"   {i}. {pl['snippet']['title']} (ID: {pl['id']})")
            print(f"   0. No playlist")
            print()

            if not args.yes:
                choice = input("Select playlist number (or press Enter for none): ").strip()
                if choice.isdigit() and 0 < int(choice) <= len(playlists):
                    args.playlist = playlists[int(choice) - 1]["id"]
                    print(f"   Selected: {playlists[int(choice) - 1]['snippet']['title']}")
        else:
            print("   (no playlists found)")

    if args.dry_run:
        print("\n[DRY RUN] No upload performed.")
        return

    # Confirmation
    if not args.yes:
        print()
        confirm = input(f"Upload to '{channel_name}'? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return

    result = upload_video(
        youtube,
        video_path,
        meta["title"],
        meta["description"],
        meta["tags"],
        meta["category"],
        args.privacy,
        args.playlist,
        publish_at,
    )

    # Upload thumbnail
    video_id = result["id"]
    print(f"\nUploading thumbnail...")
    try:
        thumb_result = update_thumbnail(youtube, video_id, thumbnail_path)
        thumb_url = thumb_result.get("items", [{}])[0].get("default", {}).get("url", "")
        print(f"   Thumbnail URL: {thumb_url}")
    except Exception as e:
        print(f"   ⚠️ Failed to upload thumbnail: {e}")

    # Save upload info
    upload_info_path = project.video_dir / "youtube_upload.json"
    upload_info = {
        "video_id": result["id"],
        "url": f"https://youtu.be/{result['id']}",
        "title": meta["title"],
        "privacy": "scheduled" if publish_at else args.privacy,
        "uploaded_at": result.get("snippet", {}).get("publishedAt"),
    }
    if publish_at:
        upload_info["scheduled_at"] = publish_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    upload_info_path.write_text(json.dumps(upload_info, indent=2, ensure_ascii=False))
    print(f"\n📝 Upload info saved to: {upload_info_path}")


if __name__ == "__main__":
    main()
