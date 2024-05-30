import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

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
    if not message.document or message.document.mime_type != 'application/pdf':
        await message.reply("Чекті жіберіңіз.")
        return

    # Download the PDF file
    file_name = message.document.file_name

    if file_name[0:18] != "transfer-receipt-№":
        await message.reply("Чекті жіберіңіз.")
        return

    # Assume paycheck ID is in the text and parse it
    paycheck_id = extract_paycheck_id(file_name)  # Implement this function as needed

    if paycheck_id in paycheck_ids:
        await message.reply("Бұл чек уже жіберілген")
    else:
        print(f"Paycheck {paycheck_id} added")
        paycheck_ids[paycheck_id] = message.from_user.username
        save_json('paycheck_ids.json', paycheck_ids)
        whitelist[message.from_user.username] = True
        save_json('whitelist.json', whitelist)
        await message.reply("Чекіңіз расталды")

    await state.clear()


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
    whitelist_text = ""
    for user in whitelist.keys():
        whitelist_text += "@" + user + "\n"
    await message.reply(f"Уайтлист қолданушылар:\n{whitelist_text}")


def extract_paycheck_id(text):
    text = text[18::]
    return text[:-4:]


async def main():
    print("Starting bot")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
