import asyncio
import logging
import pathlib

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from bs4 import BeautifulSoup
from curl_cffi import requests
from google.api_core.exceptions import InternalServerError
from google.generativeai.types import GenerationConfig, HarmBlockThreshold, HarmCategory

BOT_TOKEN = "YOUR:TOKEN"
GEMINI_API_KEY = "YOUR_API_TOKEN"

logging.basicConfig(level=logging.INFO)


class GeminiChat:
    def __init__(self, api_key, pdf_path=None):
        genai.configure(api_key=api_key)
        self.default_history = [
            {
                "role": "user",
                "parts": [
                    """Your history for solving must be here."""
                ],
            },
            {"role": "model", "parts": ["Okay, I understand."]},
        ]
        self.history = self.default_history
        self.generation_config = GenerationConfig(
            temperature=0.6,
            top_p=0.9,
            top_k=30,
        )
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        self.pdf_path = pathlib.Path(pdf_path) if pdf_path else None

        if self.pdf_path and self.pdf_path.exists():
            self._add_pdf_context_to_history()
    
    def _add_pdf_context_to_history(self):
    try:
        logging.info(f"Uploading PDF file: {self.pdf_path}")
        uploaded_file = genai.upload_file(self.pdf_path)
        logging.info(f"PDF successfully uploaded: {uploaded_file}")
        pdf_reference = f"PDF-file {self.pdf_path.name} uploaded for analysis."

        self.history.insert(0, {
            "role": "user",
            "parts": [
                pdf_reference,
                uploaded_file,
                "Here's PDF file for using it.",
            ],
        })
    except Exception as e:
        logging.error(f"Error with uploading PDF file: {e}")

    def _create_new_chat(self, history):
        model = genai.GenerativeModel(
            "gemini-2.0-flash-exp", # you can change the model
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        return model.start_chat(history=history)

    async def generate_response(self, user_input, current_history=None):
        chat_history = self.default_history + (current_history or [])
        chat = self._create_new_chat(chat_history)
        retries = 0
        max_retries = 3
        retry_delay = 5

        while retries < max_retries:
            try:
                response = await asyncio.to_thread(
                    chat.send_message,
                    user_input,
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings,
                )
                return response.text.replace("*", "")
            except InternalServerError as e:
                retries += 1
                logging.error(
                    f"Gemini API error: {e}. Retrying in {retry_delay} seconds... (Attempt {retries}/{max_retries})"
                )
                if retries < max_retries:
                    await asyncio.sleep(retry_delay)
                else:
                    raise e
            except Exception as e:
                logging.error(f"Error in get_gemini_response: {e}")
                raise e


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
gemini = GeminiChat(api_key=GEMINI_API_KEY, pdf_path=r'path/to/your/file.pdf')


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Hello! Send me Google Forms link and I will try to solve it.")


@dp.message()
async def process_link(message: types.Message):
    link = message.text
    try:
        soup = BeautifulSoup(requests.get(link).text, "html.parser")
    except Exception as e:
        logging.error(f"Error fetching URL: {e}")
        await message.answer("Error fetching URL.\nTry again later.")
        return

    question_divs = soup.find_all('div', class_='Qr7Oae')

    if not question_divs:
        await message.answer("Error handling Google Forms questions.\nTry again later.")
        return

    formatted_questions = ""
    for i, question_div in enumerate(question_divs):
        question_element = question_div.find('span', class_='M7eMe')
        if question_element:
            question_text = question_element.text.strip().replace(u'\xa0', '')
            formatted_questions += f"{i + 1}. {question_text}\n"
        else:
            continue

        answer_elements = question_div.find_all('span', class_='aDTYNe snByac OvPDhc OIC90c')
        answers_for_group = [answer.text.strip() for answer in answer_elements]
        if answers_for_group:
            formatted_questions += f"Answers: {', '.join(answers_for_group)}\n"

        list_elements = question_div.find_all('div', class_='eBFwI')
        answers_for_group = [answer.text.strip() for answer in list_elements]
        if answers_for_group:
            formatted_questions += f"Answers (multiple choice): {', '.join(answers_for_group)}\n"

        description_element = question_div.find_next_sibling('div', class_='gubaDc OIC90c RjsPE')
        if description_element and description_element.text.strip() != '':
            formatted_questions += f"Description: {description_element.text.strip()}\n"

    try:
        if not formatted_questions.strip():
            await message.answer("Failed to get questions, descriptions or answers.")
            return

        await message.answer("Please, wait...")
        response = await gemini.generate_response(formatted_questions)
        await message.answer(f"Here's the response from the AI:\n{response}")
    except Exception as e:
        logging.error(f"Error during processing: {e}")
        await message.answer("Something went wrong during processing response.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
