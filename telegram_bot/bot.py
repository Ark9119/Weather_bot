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
WEATHER_SERVICE_URL = os.getenv('WEATHER_SERVICE_URL', 'http://127.0.0.1:8001')
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://127.0.0.1:8002')


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


async def get_username_from_user_id(user_id: int) -> str:
    """
    Генерация username для Telegram пользователя.
    Используется формат telegram_{user_id} для уникальности.
    """
    return f"telegram_{user_id}"


async def get_user_city(user_id: int):
    """
    Получение города пользователя из weather_auth по Telegram user_id.
    Args:
        user_id: ID пользователя из Telegram (message.chat.id)
    Returns:
        str | None: Название города или None, если пользователь не найден
    """
    username = await get_username_from_user_id(user_id)
    api_url = f'{AUTH_SERVICE_URL}/users/{username}/city'
    try:
        data = await make_api_request(api_url, method='GET')
        if data:
            return data.get('city')
    except Exception as e:
        print(f"Ошибка при получении города из weather_auth: {e}")  # TODO
    return None


async def register_user_in_auth_service(user_id: int, city: str) -> bool:
    """
    Регистрация пользователя в weather_auth.
    Args:
        user_id: ID пользователя из Telegram
        city: Название города пользователя
    Returns:
        bool: True если регистрация успешна, False в противном случае
    """
    username = await get_username_from_user_id(user_id)
    password = str(user_id)
    api_url = f'{AUTH_SERVICE_URL}/auth/register'
    payload = {
        'username': username,
        'password': password,
        'city': city
    }
    try:
        data = await make_api_request(api_url, payload, method='POST')
        return data is not None
    except Exception as e:
        print(f"Ошибка при регистрации в weather_auth: {e}")
        return False


async def update_user_city_in_auth_service(user_id: int, city: str) -> bool:
    """
    Обновление города пользователя в weather_auth.
    Для этого нужно сначала получить токен.
    """
    username = await get_username_from_user_id(user_id)
    password = str(user_id)
    login_url = f'{AUTH_SERVICE_URL}/auth/login'
    login_payload = {
        'username': username,
        'password': password
    }
    try:
        login_data = await make_api_request(
            login_url, login_payload, method='POST'
        )
        if not login_data or 'access_token' not in login_data:
            return False
        token = login_data['access_token']
        update_url = f'{AUTH_SERVICE_URL}/users/me/city'
        update_payload = {'city': city}
        async with aiohttp.ClientSession() as session:
            async with session.put(
                update_url,
                json=update_payload,
                headers={'Authorization': f'Bearer {token}'}
            ) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    print(
                        f'Ошибка при обновлении города: {response.status} '
                        f'- {error_text}'
                    )
                    return False
    except Exception as e:
        print(f"Ошибка при обновлении города пользователя: {e}")
        return False


async def save_user_city(user_id: int, city: str | None):
    """
    Сохранение города пользователя в weather_auth.
    Если пользователь не существует, сначала регистрирует его.
    """
    if not city:
        raise ValueError("Город не может быть пустым")
    # Проверяем, существует ли пользователь
    existing_city = await get_user_city(user_id)
    if existing_city is None:
        # Пользователь не существует, регистрируем его
        success = await register_user_in_auth_service(user_id, city)
        if not success:
            raise ValueError("Не удалось зарегистрировать пользователя")
    else:
        # Пользователь существует, обновляем город
        success = await update_user_city_in_auth_service(user_id, city)
        if not success:
            raise ValueError("Не удалось обновить город пользователя")


async def get_weather_data(user_id: int, endpoint: str, days: int):
    """
    Получает данные о погоде.
    Использует username вместо user_id для запроса к Weather API.
    """
    username = await get_username_from_user_id(user_id)
    api_url = f'{WEATHER_SERVICE_URL}/weather/{endpoint}/'
    payload = {
        'user': username,
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
    Команда старт. Проверяет пользователя в weather_auth,
    если его нет - просит ввести город.
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
    user_id = message.chat.id

    try:
        await save_user_city(user_id, city)
        saved_city = await get_user_city(user_id)
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
        'Привет! 👋\n\n'
        'Я ваш погодный бот. Для начала работы нажмите кнопку "Старт".',
        reply_markup=start_keyboard
    )


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
