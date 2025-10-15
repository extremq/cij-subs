import argparse
import re
import requests
import time
import random
import os
from sanitize_filename import sanitize
from pydantic import BaseModel

class Video(BaseModel):
    video_id: int
    title: str
    transcript_id: int

def fetch_with_backoff(session, url, max_retries=5, initial_delay=1):
    for attempt in range(max_retries):
        try:
            response = session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise Exception(
                    f"Failed to fetch after {max_retries} attempts: {e}"
                )

            delay = initial_delay * (2**attempt) + random.uniform(0, 1)
            print(f"Attempt {attempt + 1} failed. Retrying in {delay:.2f} seconds...")
            time.sleep(delay)

def decimal_to_vtt_time(decimal_seconds):
    seconds = int(decimal_seconds)
    milliseconds = int((decimal_seconds - seconds) * 1000)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

def process_video(session, video: Video):
    transcript_url = (
        f"https://cijapanese.com/api/v1/transcript?transcriptId={video.transcript_id}"
    )
    transcript_data = fetch_with_backoff(session, transcript_url)

    raw = ""
    vtt = "WEBVTT\n\n"
    for idx, cue in enumerate(transcript_data["data"]["cues"]):
        vtt += f"{idx}\n"
        vtt += f"{decimal_to_vtt_time(cue["time"]["start"])} --> {decimal_to_vtt_time(cue["time"]["end"])}\n"
        vtt += f"{cue["text"]}\n\n"

        if cue["newParagraph"]:
            raw += "\n"
        raw += cue["text"]

    os.makedirs("transcripts", exist_ok=True)
    with open(f"transcripts/{video.video_id:04} {sanitize(video.title)}.vtt", "w", encoding="utf-8") as f:
        f.write(vtt)

    with open(f"transcripts/{video.video_id:04} {sanitize(video.title)}.txt", "w", encoding="utf-8") as f:
        f.write(raw)


def validate_and_parse_input(input_str):
    if input_str == "all":
        return set()

    pattern = r"^(\d+|\d+-\d+)(,(\d+|\d+-\d+))*$"
    if not re.fullmatch(pattern, input_str):
        raise ValueError(
            f"Invalid input format: {input_str}. Expected numbers or ranges (e.g., 1,4-6,9-10)."
        )

    parts = input_str.split(",")
    numbers = set()

    for part in parts:
        if "-" in part:
            start, end = map(int, part.split("-"))
            if start > end:
                raise ValueError(f"Invalid range: {part}. Start must be <= end.")
            numbers.update(range(start, end + 1))
        else:
            numbers.add(int(part))

    return numbers


def get_existing_ids():
    existing_ids = set()
    if os.path.exists("transcripts"):
        for filename in os.listdir("transcripts"):
            if filename.endswith(".vtt"):
                try:
                    id_str = filename.split()[0]
                    existing_ids.add(int(id_str))
                except (IndexError, ValueError):
                    print(f"Skipped {filename}.")
                    continue
    
    if len(existing_ids) > 0:
        print(f"Found {len(existing_ids)} already existing videos. Will skip them.")

    return existing_ids

def main():
    parser = argparse.ArgumentParser(description="CIJ subs downloader")
    parser.add_argument(
        "ids",
        type=str,
        help='List of numbers and ranges (e.g., 1 4-6 "2,5-7,9-10"). IDs found in transcripts/ '
        "will be removed from your list, so we do not double-download. Can also use `all` to download everything.",
    )
    args = parser.parse_args()

    try:
        ids = validate_and_parse_input(args.ids)
    except ValueError as e:
        print(f"Error: {e}")

    with requests.Session() as session:
        # fetch all content
        website_content = fetch_with_backoff(session, "https://cijapanese.com/api/v1/content")

        # get max id if user wants everything
        if len(ids) == 0:
            max_id = 1
            for video in website_content["data"]["modules"]:
                max_id = max(max_id, video["id"])
            
            print(f"Fetching up everything up until {max_id}")
            ids = set(range(1, max_id + 1))        

        # remove intersection
        existing_ids = get_existing_ids()
        if len(existing_ids) > 0:
            ids -= existing_ids

        # collect all videos
        videos = []
        for video in website_content["data"]["modules"]:
            if video["id"] not in ids:
                continue

            if "plan" not in video:
                continue

            if "transcriptId" not in video["plan"]:
                continue

            videos.append(Video(
                video_id=video["id"],
                title=f"{video["plan"]["titleJP"]} | {video["plan"]["titleEN"]}",
                transcript_id=video["plan"]["transcriptId"]
            ))

        # process videos
        for video in videos:
            try:
                process_video(session, video)
                print(f"Video ID {video.video_id}: Done")
            except Exception as e:
                print(f"Video ID {video.video_id}: Error - {e}")

            # We care about their server.
            # Please have some kind of pause between requests
            time.sleep(1/5)


if __name__ == "__main__":
    main()
