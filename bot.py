import os
import json
import asyncio
import pandas as pd
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
from PIL import Image
import pytesseract

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMIN_PASSWORD = os.getenv("PASSWORD")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# State definitions for FSM
class Form(StatesGroup):
    waiting_for_pdf = State()
    waiting_for_password = State()


# Load or initialize JSON files
def load_json(filename):
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json(filename, data):
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)


paycheck_ids = load_json('paycheck_ids.json')
whitelist = load_json('whitelist.json')
admins = load_json('admins.json')


# Handle the /start command
@dp.message(CommandStart())
async def send_welcome(message: Message, state: FSMContext):
    print(f"{message.from_user.username} started")
    await message.reply("Қош келдіңіз, чекті жіберіңіз.")
    await state.set_state(Form.waiting_for_pdf)


# Handle receiving PDF
@dp.message(Form.waiting_for_pdf)
async def handle_pdf(message: types.Message, state: FSMContext):
    if message.content_type == types.ContentType.PHOTO:
        await handle_photo(message, state)
    elif message.document.mime_type == 'application/pdf':
        # Download the PDF file
        file_name = message.document.file_name

        if file_name[0:18] != "transfer-receipt-№":
            await message.reply("Чекті жіберіңіз.")
            return

        # Assume paycheck ID is in the text and parse it
        paycheck_id = extract_paycheck_id(file_name)  # Implement this function as needed
        await process_paycheck_id(message, paycheck_id, state)
    else:
        await message.reply("Чекті жіберіңіз.")
        return


async def handle_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    await bot.download_file(file_path, 'paycheck.jpg')

    image = Image.open('paycheck.jpg')
    text = pytesseract.image_to_string(image)
    os.remove('paycheck.jpg')

    paycheck_id = extract_paycheck_id_from_photo(text)
    await process_paycheck_id(message, paycheck_id, state)


async def process_paycheck_id(message, paycheck_id, state):
    if paycheck_id in paycheck_ids:
        await message.reply("Бұл чек уже жіберілген")
        return
    else:
        print(f"Paycheck {paycheck_id} added")
        paycheck_ids[paycheck_id] = message.from_user.username
        save_json('paycheck_ids.json', paycheck_ids)
        whitelist[message.from_user.username] = True
        save_json('whitelist.json', whitelist)
        await message.reply("Чекіңіз расталды")

    await state.clear()


def extract_paycheck_id_from_photo(text):
    # Implement the logic to extract the paycheck ID from the text
    # Example logic: Find the first occurrence of "QR" followed by digits
    import re
    pattern = r'QR\d+'

    # Search for the pattern in the text
    match = re.search(pattern, text)

    return str(match.group(0))[1::]


# Handle admin password and send whitelist
@dp.message(Command('admin'))
async def admin_login(message: types.Message, state: FSMContext):
    if message.from_user.username in admins:
        await send_whitelist(message)
    else:
        await message.reply("Парольды енгізіңіз")
        await state.set_state(Form.waiting_for_password)


@dp.message(Form.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        print(f"{message.from_user.username} is now admin")
        admins[message.from_user.username] = True
        save_json('admins.json', admins)
        await send_whitelist(message)
    else:
        await message.reply("Қате пароль")

    await state.clear()


async def send_whitelist(message: types.Message):
    print(f"Sending whitelist to {message.from_user.username}")
    await generate_and_send_whitelist_excel(message)


async def generate_and_send_whitelist_excel(message: types.Message):
    # Create a DataFrame from the whitelist
    df = pd.DataFrame(list(whitelist.keys()), columns=["Username"])

    # Save the DataFrame to an Excel file
    file_path = "whitelist.xlsx"
    df.to_excel(file_path, index=False)

    # Send the Excel file
    await bot.send_document(message.chat.id, types.FSInputFile(file_path))

    # Remove the file after sending
    os.remove(file_path)


def extract_paycheck_id(text):
    text = text[21::]
    return text[:-4:]


async def main():
    print("Starting bot")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
