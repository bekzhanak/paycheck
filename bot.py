import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

from utils import *

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

paychecks = load_json('paychecks.json')
whitelist = load_json('whitelist.json')
admins = load_json('admins.json')


# Handle the /start command
@dp.message(CommandStart())
async def send_welcome(message: Message, state: FSMContext):
    print(f"{message.from_user.username} started")
    await message.reply("Добро пожаловать, отправьте чек")
    await state.set_state(Form.waiting_for_pdf)


# Handle receiving PDF
@dp.message(Form.waiting_for_pdf)
async def handle_pdf(message: types.Message, state: FSMContext):
    if not message.document or message.document.mime_type != "application/pdf":
        await message.reply("Отправьте чек")
        return

    try:
        pdf = "check.pdf"
        await bot.download(message.document, pdf)
        pdf_data = parse_pdf(pdf)
        online_data = parse_online_receipt(pdf)
    except Exception as e:
        await message.reply("Этот чек не корректен")
        print(e)
        return

    if pdf_data != online_data:
        await message.reply("Данные не соответствуют")
        return

    os.remove("check.pdf")
    await process_paycheck(message, online_data, state)


async def process_paycheck(message, paycheck_data, state):
    paycheck_id = paycheck_data["check_number"]
    if paycheck_id in paychecks:
        await message.reply("Данный чек уже был отправлен")
        return

    print(f"Paycheck {paycheck_id} added")
    paychecks[paycheck_id] = paycheck_data
    save_json('paychecks.json', paychecks)
    whitelist[message.from_user.username] = True
    save_json('whitelist.json', whitelist)
    await message.reply("Чек валидирован")

    await state.clear()


# Handle admin password and send whitelist
@dp.message(Command('admin'))
async def admin_login(message: types.Message, state: FSMContext):
    if message.from_user.username in admins:
        await send_whitelist(message, bot, whitelist)
    else:
        await message.reply("Введите пароль")
        await state.set_state(Form.waiting_for_password)


@dp.message(Form.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        print(f"{message.from_user.username} is now admin")
        admins[message.from_user.username] = True
        save_json('admins.json', admins)
        await send_whitelist(message, bot, whitelist)
    else:
        await message.reply("Неправильный пароль")

    await state.clear()


async def main():
    print("Starting bot")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
