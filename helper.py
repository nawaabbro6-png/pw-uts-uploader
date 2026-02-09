import logging
import subprocess
import datetime
import asyncio
import os
import requests
import time
from p_bar import progress_bar
from config import LOG
import aiohttp
import tgcrypto
import aiofiles
from pyrogram.types import Message
from pyrogram import Client, filters

failed_counter = 0


def duration(filename):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filename
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    try:
        return float(result.stdout)
    except Exception:
        return 0.0


async def download(url, name):
    ka = f"{name}.pdf"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                async with aiofiles.open(ka, mode="wb") as f:
                    await f.write(await resp.read())
    return ka


async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    print(f"[{cmd!r} exited with {proc.returncode}]")
    if proc.returncode == 1:
        return False
    if stdout:
        return f"[stdout]\n{stdout.decode()}"
    if stderr:
        return f"[stderr]\n{stderr.decode()}"


def old_download(url, file_name, chunk_size=3072 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, "wb") as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name


def human_readable_size(size, decimal_places=2):
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 3072.0 or unit == "PB":
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"


async def download_video(url, cmd, name):
    global failed_counter

    download_cmd = (
        f'{cmd} -R 25 --fragment-retries 25 '
        '--external-downloader aria2c '
        '--downloader-args "aria2c: -x 16 -j 32"'
    )

    print(download_cmd)
    logging.info(download_cmd)

    k = subprocess.run(download_cmd, shell=True)

    if "visionias" in cmd and k.returncode != 0 and failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        return await download_video(url, cmd, name)

    failed_counter = 0

    try:
        if os.path.isfile(name):
            return name
        if os.path.isfile(f"{name}.webm"):
            return f"{name}.webm"

        base = os.path.splitext(name)[0]

        if os.path.isfile(f"{base}.mkv"):
            return f"{base}.mkv"
        if os.path.isfile(f"{base}.mp4"):
            return f"{base}.mp4"
        if os.path.isfile(f"{base}.mp4.webm"):
            return f"{base}.mp4.webm"

        return name
    except Exception:
        return name


async def send_vid(bot: Client, m: Message, cc, filename, thumb, name):

    subprocess.run(
        f'ffmpeg -i "{filename}" -ss 00:01:00 -vframes 1 "{filename}.jpg"',
        shell=True
    )

    try:
        if thumb == "no":
            thumbnail = f"{filename}.jpg"
        else:
            thumbnail = thumb
    except Exception as e:
        await m.reply_text(str(e))
        thumbnail = None

    dur = int(duration(filename))
    start_time = time.time()

    try:
        copy = await bot.send_video(
            chat_id=m.chat.id,
            video=filename,
            caption=cc,
            supports_streaming=True,
            height=720,
            width=1280,
            thumb=thumbnail,
            duration=dur
        )
        await copy.copy(chat_id=LOG)

    except TimeoutError:
        await asyncio.sleep(5)
        copy = await bot.send_video(
            chat_id=m.chat.id,
            video=filename,
            caption=cc,
            supports_streaming=True,
            height=720,
            width=1280,
            thumb=thumbnail,
            duration=dur
        )
        await copy.copy(chat_id=LOG)

    except Exception:
        copy = await bot.send_video(
            chat_id=m.chat.id,
            video=filename,
            caption=cc,
            supports_streaming=True,
            height=720,
            width=1280,
            thumb=thumbnail,
            duration=dur
        )
        await copy.copy(chat_id=LOG)

    if os.path.exists(filename):
        os.remove(filename)

    if os.path.exists(f"{filename}.jpg"):
        os.remove(f"{filename}.jpg")
