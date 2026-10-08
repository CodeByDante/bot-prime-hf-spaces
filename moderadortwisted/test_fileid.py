import asyncio
from pyrogram.file_id import FileId

# Mock file id format from a typical Telegram document
fid_string = "BQACAgQAAxkBAAE...mocked..."

try:
    decoded = FileId.decode(fid_string)
    print(dir(decoded))
except Exception as e:
    print(e)
