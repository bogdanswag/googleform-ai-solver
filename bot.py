import asyncio
import logging

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
    def __init__(self, api_key):
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
gemini = GeminiChat(api_key=GEMINI_API_KEY)


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

    question_elements = soup.find_all('span', class_='M7eMe')

    if not question_elements:
        await message.answer("Error handling Google Forms questions.\nTry again later.")
        return

    formatted_questions = ""
    for i, question in enumerate(question_elements):
        question_text = question.text.strip().replace(u'\xa0', '')
        formatted_questions += f"{i + 1}. {question_text}\n"

        parent_div = question.find_parent('div', class_='z12JJ')
        if parent_div:
            answer_group_elements = parent_div.find_all('div', class_='SG0AAe')
            if answer_group_elements:
                for answer_group in answer_group_elements:
                    answer_elements = answer_group.find_all('span', class_='aDTYNe snByac OvPDhc OIC90c')
                    answers_for_group = [answer.text.strip() for answer in answer_elements]
                    if answers_for_group:
                        formatted_questions += f"Answers: {', '.join(answers_for_group)}\n"
                continue

        description_element = question.find_parent('div').find_next_sibling('div', class_='gubaDc OIC90c RjsPE')
        if description_element:
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
