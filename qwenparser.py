import logging
import re

# Убедись, что логирование настроено (в начале файла)
logging.basicConfig(level=logging.INFO)

def parse_order(text):
    """Извлекает данные заказа из текста между метками [ORDER_START] и [ORDER_END]"""
    logging.info("🔍 Запущен парсер заказов...")

   # Улучшенная регулярка: игнорируем регистр и возможные пробелы/переводы строк
    pattern = re.compile( 
        r"\[ORDER_START\](?:\s|&nbsp;)*((?:(?!\[ORDER_END\])[\s\S])*)\[ORDER_END\]",                 
        re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(text)

    if not match:
        logging.warning("❌ Блок [ORDER_START]...[ORDER_END] не найден в ответе модели.")
        return None

    order_block = match.group(1).strip()
    logging.info(f"📦 Найден блок заказа:\n{order_block}")

    order_data = {}

    # Парсим каждую строку
    for line in order_block.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            order_data[key.strip()] = value.strip()
            logging.debug(f"📌 Получено поле: {key} → {value}")
        else:
            logging.warning(f"⚠️ Пропущена строка (отсутствует двоеточие): {line}")

    # Проверяем обязательные поля
    required_fields = ['Имя', 'Адрес', 'Товар', 'Количество']
    missing = [field for field in required_fields if field not in order_data]

    if missing:
        logging.error(f"❌ Ошибка: отсутствуют обязательные поля: {missing}")
        return None

    # Валидация количества
    # try:
    #     quantity = int(order_data['Количество'])
    #     if quantity <= 0:
    #         raise ValueError("Количество должно быть положительным числом")
    #     order_data['Количество'] = quantity
    #     logging.info("✅ Количество успешно проверено.")
    # except ValueError as e:
    #     logging.error(f"❌ Ошибка валидации количества: {e}")
    #     return None

    logging.info(f"✅ Заказ успешно распознан: {order_data}")
    return order_data
