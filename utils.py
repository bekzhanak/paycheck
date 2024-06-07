import os
import re
import json
import requests
import PyPDF2
from bs4 import BeautifulSoup
from pdf2image import convert_from_path
import cv2
from aiogram import types
import pandas as pd


def load_json(filename):
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json(filename, data):
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)


def parse_pdf(pdf_path):
    text = extract_text_from_pdf(pdf_path)

    return {
        "price": extract_price_from_pdf_text(text)[:-2:],
        "check_number": extract_check_number_from_pdf_text(text),
        "name": extract_name_from_pdf_text(text)
    }


def extract_text_from_pdf(pdf_path):
    # Open the PDF file
    with open(pdf_path, 'rb') as file:
        # Create a PDF reader object
        reader = PyPDF2.PdfReader(file)

        # Initialize a variable to store the extracted text
        text = ""

        # Iterate over all the pages in the PDF
        for page_num in range(len(reader.pages)):
            # Get the page
            page = reader.pages[page_num]

            # Extract text from the page
            text += page.extract_text() + "\n"

    return text


def extract_price_from_pdf_text(text):
    # Use regex to find the price in the text
    price_pattern = r'\d{1,3}(?: \d{3})* ₸'
    match = re.search(price_pattern, text)
    if match:
        return match.group(0)
    return None


def extract_check_number_from_pdf_text(text):
    # Use regex to find the check number starting with QR
    match = re.search(r'QR\d+', text)
    return match.group(0) if match else None


def extract_name_from_pdf_text(text):
    # Use regex to find the name of the person
    match = re.search(r'ФИО плательщика (.+)', text)
    return match.group(1).strip() if match else None


def parse_online_receipt(pdf):
    link = extract_qr_code_from_pdf(pdf)
    html = fetch_html(link)
    return parse_html(html)


def fetch_html(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Find price
    price_element = soup.find('span', class_='amount-value')
    price = price_element.get_text(strip=True) if price_element else None

    # Find check number
    check_number_element = soup.find('div', class_='name', text=lambda x: x and '№ чека' in x)
    check_number = check_number_element.find_next('div', class_='value').get_text(
        strip=True) if check_number_element else None

    # Find name of the person
    name_element = soup.find('div', class_='name', text=lambda x: x and 'ФИО плательщика' in x)
    name = name_element.find_next('div', class_='value').get_text(strip=True) if name_element else None

    return {
        "price": price[:-1:],
        "check_number": check_number,
        "name": name
    }


def extract_qr_code_from_pdf(pdf_path):
    # Convert PDF to images
    images = convert_from_path(pdf_path)

    # Initialize QR Code detector
    qcd = cv2.QRCodeDetector()

    for image in images:
        # Save image temporarily to disk
        temp_image_path = "temp_image.jpg"
        image.save(temp_image_path)

        # Read the saved image
        image = cv2.imread(temp_image_path)

        # Detect and decode QR codes
        ret_qr, decoded_info, points, _ = qcd.detectAndDecodeMulti(image)

        # Remove the temporary image file
        os.remove(temp_image_path)

        # Return the first decoded text if found
        if ret_qr:
            for info in decoded_info:
                if info:
                    return info

    return None


async def send_whitelist(message: types.Message, bot, whitelist):
    print(f"Sending whitelist to {message.from_user.username}")
    await generate_and_send_whitelist_excel(message, bot, whitelist)


async def generate_and_send_whitelist_excel(message: types.Message, bot, whitelist):
    # Create a DataFrame from the whitelist
    df = pd.DataFrame(list(whitelist.keys()), columns=["Username"])

    # Save the DataFrame to an Excel file
    file_path = "whitelist.xlsx"
    df.to_excel(file_path, index=False)

    # Send the Excel file
    await bot.send_document(message.chat.id, types.FSInputFile(file_path))

    # Remove the file after sending
    os.remove(file_path)
