from datetime import datetime


def mapping_weather_for_days(city, forecast):
    """Для прогноза на несколько дней с почасовыми данными"""
    user_city = city
    found_country = forecast['found_country']
    found_city = forecast['found_city']
    date = forecast['date']
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    formatted_date = date_obj.strftime('%d.%m.%Y')
    min_temp_c = min(forecast['temp_c'])
    max_temp_c = max(forecast['temp_c'])
    avg_temp = sum(forecast['temp_c']) / len(forecast['temp_c'])
    clouds = forecast['cloud']
    humidity = forecast['humidity']
    rain_chance = forecast['chance_of_rain']

    avg_cloud = sum(clouds) / len(clouds)
    avg_humidity = sum(humidity) / len(humidity)
    max_rain_chance = max(rain_chance)

    text = (
        f'По Вашему запросу: {user_city}\n'
        f'Найден город {found_city} в {found_country}.\n'
        f'📅 {formatted_date} с 00:00 до 23:00:\n'
        f'🌡  Температура: {min_temp_c:.1f}°C...{max_temp_c:.1f}°C'
        f'(ср. {avg_temp:.1f}°C)\n'
        f'☁️  Облачность: {avg_cloud:.0f}%\n'
        f'💧 Влажность: {avg_humidity:.0f}%\n'
        f'🌧  Вероятность дождя: {max_rain_chance:.0f}%\n'
    )
    return text


def mapping_weather_for_now(city, forecast):
    """Для текущей погоды (данные на один момент времени)"""
    user_city = city
    found_country = forecast['found_country']
    found_city = forecast['found_city']
    date = forecast['date']
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    formatted_date = date_obj.strftime('%d.%m.%Y')
    temp_c = forecast['temp_c']
    cloud = forecast['cloud']
    humidity = forecast['humidity']
    rain_chance = forecast['chance_of_rain']

    weather_emoji, weather_status = weather_emoji_status(rain_chance, cloud)

    text = (
        f'По Вашему запросу: {user_city}\n'
        f'Найден город {found_city} в {found_country}.\n'
        f'📅 {formatted_date}\n'
        f'🌡  Температура: {temp_c:.1f}°C\n'
        f'☁️  Облачность: {cloud}%\n'
        f'💧 Влажность: {humidity}%\n'
        f'🌧  Вероятность дождя: {rain_chance}%\n'
        f'📊 Состояние: {weather_emoji} {weather_status}'
    )
    return text


def weather_emoji_status(rain_chance, cloud):
    # Определяем состояние погоды для эмодзи
    if rain_chance > 50:
        weather_emoji = "🌧️"
        weather_status = "Дождь"
    elif cloud > 70:
        weather_emoji = "☁️"
        weather_status = "Облачно"
    elif cloud > 30:
        weather_emoji = "⛅"
        weather_status = "Переменная облачность"
    else:
        weather_emoji = "☀️"
        weather_status = "Ясно"
    return weather_emoji, weather_status
