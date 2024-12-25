import asyncio
import logging

from curl_cffi import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from google.api_core.exceptions import InternalServerError
from google.generativeai.types import GenerationConfig, HarmBlockThreshold, HarmCategory

class GeminiChat:
    def __init__(self, api_key="YOUR_API_KEY"):
        genai.configure(api_key=api_key)
        self.default_history = [
            {
                "role": "user",
                "parts": [
                    """YOUR HISTORY FOR SOLVING TESTS."""
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

async def main():
    link = 'your_google_form_link'
    soup = BeautifulSoup(requests.get(link).text, "html.parser")

    question_elements = soup.find_all('span', class_='M7eMe')
    answer_group_elements = soup.find_all('div', class_='SG0AAe')

    questions = []
    for question in question_elements:
        questions.append(question.text.strip().replace(u'\xa0', ''))

    all_answers = []
    for answer_group in answer_group_elements:
        answer_elements = answer_group.find_all('span', class_='aDTYNe snByac OvPDhc OIC90c')
        answers_for_group = []
        for answer in answer_elements:
            answers_for_group.append(answer.text.strip())
        all_answers.append(answers_for_group)

    parsed_text = list(zip(questions, all_answers))

    gemini = GeminiChat()

    formatted_questions = ""
    for i, (question, answers) in enumerate(parsed_text):
        formatted_questions += f"{i + 1}. {question}\nAnswers: {', '.join(answers)}\n"

    response = await gemini.generate_response(formatted_questions)
    print(response)

if __name__ == "__main__":
    asyncio.run(main())