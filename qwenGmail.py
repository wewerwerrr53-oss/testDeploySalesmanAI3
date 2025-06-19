import smtplib
from email.mime.text import MIMEText
import logging
import os

# Функция отправки заказа на email
def send_order_to_email(order_data):
    """Отправляет данные заказа на email"""
    try:
        sender = os.getenv("GMAIL_USER")
        password = os.getenv("GMAIL_PASSWORD")
        receiver = os.getenv("RECEIVER_EMAIL")

        # Формируем сообщение
        message = MIMEText("\n".join([f"{key}: {value}" for key, value in order_data.items()]))
        message['From'] = sender
        message['To'] = receiver
        message['Subject'] = 'Новый заказ из Telegram-бота'

        # Отправка
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receiver, message.as_string())
            
        return True
        
    except Exception as e:
        logging.error(f"Ошибка отправки email: {e}")
        return False