# CIJ subs downloader
This is a simple script that downloads the subtitles from CIJ so you can use them with other players (e.g. ASB player).

This respects the website's server by using exponential backoff and a pause between requests. This script could clearly be improved by using a pool of requests to increase speed, but my intention is to not disturb the CIJ api in any way.

## Requirements
- Python 3
- `requests` library
- `pydantic` library 

Install the libraries using `pip install requests pydantic`.

If you use `uv`, just do `uv run main.py`.

## Usage
```bash
python main.py 1,2,5-10,12
# or
python main.py all # to download everything
# or
uv run main.py 1,2,5-10,12
```
> `1,2,5-10,12` will download subtitles for video IDs 1, 2, 5, 6, 7, 8, 9, 10, and 12.

Subtitles are saved in `transcripts`. If a video's subtitles are found in the directory, they will not be downloaded again, so if you just want to keep your full collection updated, you can simply run with the `all` argument and it will figure out what you are missing.