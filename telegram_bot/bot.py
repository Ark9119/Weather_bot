import os
import asyncio
import aiohttp
from aiogram import Bot, types, Router, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from dotenv import load_dotenv
from response_transformation import (
    mapping_weather_for_days,
    mapping_weather_for_now
)

load_dotenv()

TOKEN = os.getenv('TOKEN_TELEGRAM')
bot = Bot(token=str(TOKEN))
dp = Dispatcher()
router = Router()
dp.include_router(router)


class WeatherStates(StatesGroup):
    waiting_city = State()


start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Старт')]
    ],
    resize_keyboard=True
)


main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Изменить город')],
        [
            KeyboardButton(text='Погода на 3 дня'),
            KeyboardButton(text='Погода сегодня'),
            KeyboardButton(text='Погода сейчас')
        ]
    ],
    resize_keyboard=True
)


async def make_api_request(
    api_url: str,
    payload: dict = {},
    method: str = 'POST'
):
    """Универсальная функция для API-запросов"""
    async with aiohttp.ClientSession() as session:
        async with session.request(method, api_url, json=payload) as response:
            try:
                data = (
                    await response.json()
                )
            except Exception:
                data = None
            if response.status == 200:
                return data
            elif response.status == 400:
                if data and isinstance(data, dict):
                    # Извлекаем первую ошибку из любого поля
                    for field, errors in data.items():
                        if isinstance(errors, list) and errors:
                            error_msg = errors[0]  # Берем первую ошибку
                            print(f'error_msg list {error_msg}')
                            break
                        elif isinstance(errors, str):
                            error_msg = errors
                            print(f'error_msg str {error_msg}')
                            break
                    else:
                        error_msg = 'Неизвестная ошибка валидации'
                else:
                    error_msg = await response.text() or 'Неизвестная ошибка'
                raise ValueError(error_msg)
            else:  # проверка на 500
                error_msg = await response.text()
                raise Exception(f'Сервис недоступен: {error_msg}')


async def get_user_city(user_id: int):
    """Получение города пользователя"""
    api_url = f'http://127.0.0.1:8000/city/{user_id}/'
    data = await make_api_request(api_url, method='GET')
    return data.get('city')


async def save_user_city(user_id: int, city: str | None):
    """Сохраняет город для пользователя"""
    api_url = 'http://127.0.0.1:8000/city/'
    payload = {'city': city, 'user': user_id}
    return await make_api_request(api_url, payload)


async def get_weather_data(user_id: int, endpoint: str, days: int):
    """Получает данные о погоде"""
    api_url = f'http://127.0.0.1:8000/weather/{endpoint}/'
    payload = {
        'user': user_id,
        'days': days
    }
    data = await make_api_request(api_url, payload)
    city = data.get('city')
    forecast = data.get('forecast')
    return city, forecast


@router.message(CommandStart())
@router.message(F.text == 'Старт')
async def start_cmd(message: types.Message, state: FSMContext):
    """
    Команда старт. Проверяет по ID пользователя, если его нет в базе апи
    - просит ввести город, если есть - здоровается
    """
    user_id = message.chat.id
    city = await get_user_city(user_id)

    if not city:
        await message.answer(
            'Добро пожаловать! 👋\n\n'
            'Я ваш погодный бот. Для начала работы нужно указать ваш город.\n'
            'Пожалуйста, введите название города:',
            reply_markup=ReplyKeyboardRemove()
        )
        await state.update_data(user_id=user_id)
        await state.set_state(WeatherStates.waiting_city)
    else:
        await message.answer(
            f'С возвращением! ✅\n\n'
            f'Ваш текущий город: {city}\n'
            'Выберите опцию из меню ниже:',
            reply_markup=main_menu_keyboard
        )


@router.message(WeatherStates.waiting_city)
async def process_city(message: types.Message, state: FSMContext):
    city = message.text
    user_data = await state.get_data()
    user_id = user_data.get('user_id', message.chat.id)

    try:
        data = await save_user_city(user_id, city)
        saved_city = data.get('city')
        await message.answer(
            f'Город {saved_city} успешно сохранен!',
            reply_markup=main_menu_keyboard
        )
        await state.clear()
    except ValueError as e:
        await message.answer(
            f'❌ {str(e)}\n'
            'Пожалуйста, попробуйте еще раз:',
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        # Обработка ошибки 500 (проблемы с сервером)
        await message.answer(
            f'❌ Произошла ошибка сервера {e}. Пожалуйста, попробуйте позже.',
            reply_markup=ReplyKeyboardRemove()
        )


async def handle_weather_request(
    message: types.Message,
    state: FSMContext,
    endpoint: str,
    days: int
):
    """Общая функция для обработки запросов погоды"""
    user_id = message.chat.id

    try:
        city, forecast = await get_weather_data(user_id, endpoint, days)
        for day in forecast:
            if endpoint == 'weather_to_days' or endpoint == 'today':
                await message.answer(mapping_weather_for_days(city, day))
            elif endpoint == 'now':
                await message.answer(mapping_weather_for_now(city, day))
    except ValueError as e:
        # Обработка ошибки 400 (город не найден)
        await message.answer(
            f'❌ {str(e)}\n'
            'Пожалуйста, укажите ваш город еще раз:',
            reply_markup=ReplyKeyboardRemove()
        )
        await state.update_data(user_id=user_id)
        await state.set_state(WeatherStates.waiting_city)
    except Exception as e:
        # Обработка ошибки 500 (проблемы с сервером)
        await message.answer(
            f'❌ Произошла ошибка сервера {e}. Пожалуйста, попробуйте позже.'
        )


@router.message(F.text == 'Изменить город')
async def change_city(message: types.Message, state: FSMContext):
    await state.update_data(user_id=message.chat.id)
    await message.answer(
        'Введите название вашего города:',
        reply_markup=ReplyKeyboardRemove()
        )
    await state.set_state(WeatherStates.waiting_city)


@router.message(F.text == 'Погода на 3 дня')
async def weather_3_days(message: types.Message, state: FSMContext):
    await handle_weather_request(message, state, 'weather_to_days', 3)


@router.message(F.text == 'Погода сегодня')
async def weather_today(message: types.Message, state: FSMContext):
    await handle_weather_request(message, state, 'today', 1)


@router.message(F.text == 'Погода сейчас')
async def weather_now(message: types.Message, state: FSMContext):
    await handle_weather_request(message, state, 'now', 1)


@router.message()
async def handle_any_message(message: types.Message):
    """Обработчик любого сообщения от пользователей,
    которые еще не начали работу.
    """
    await message.answer(
        "Привет! 👋\n\n"
        "Я ваш погодный бот. Для начала работы нажмите кнопку 'Старт'.",
        reply_markup=start_keyboard
    )


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
