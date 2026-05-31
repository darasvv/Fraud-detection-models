#!/usr/bin/env python
# coding: utf-8

# In[1]:


import joblib
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
import os
import nest_asyncio

import psycopg2
from datetime import datetime

nest_asyncio.apply()


# In[2]:


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MODEL_PATH = "ensemble_my_models.pkl" 


# In[ ]:


def log_to_postgres(user_id, amount, city_pop, lat, lon, merch_lat, merch_long, 
                    hour, distance_km, is_fraud, probability, risk_message):
    """Сохраняет предсказание в PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="fraud_db",
            user="fraud_user",
            password="123"
        )
        cur = conn.cursor()
        
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prediction_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id VARCHAR(100),
                amount FLOAT,
                city_pop FLOAT,
                lat FLOAT,
                lon FLOAT,
                merch_lat FLOAT,
                merch_long FLOAT,
                hour INT,
                distance_km FLOAT,
                is_fraud BOOLEAN,
                probability FLOAT,
                risk_message TEXT
            )
        """)
        
        
        cur.execute("""
            INSERT INTO prediction_logs 
            (user_id, amount, city_pop, lat, lon, merch_lat, merch_long, 
             hour, distance_km, is_fraud, probability, risk_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (str(user_id), amount, city_pop, lat, lon, merch_lat, merch_long, 
              hour, distance_km, is_fraud, probability, risk_message))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"Сохранено в PostgreSQL")
    except Exception as e:
        print(f"Ошибка PostgreSQL: {e}")
        

try:
    model = joblib.load(MODEL_PATH)
    print("Модель загружена")
except Exception as e:
    print(f"Ошибка: {e}")
    model = None

def predict_fraud(amount, city_pop, client_lat, client_lon, merch_lat, merch_lon, hour, distance_km):
    data = pd.DataFrame({
        'amt': [amount],
        'city_pop': [city_pop],
        'lat': [client_lat],
        'long': [client_lon],
        'merch_lat': [merch_lat],
        'merch_long': [merch_lon],
        'hour': [hour],
        'distance_km': [distance_km]
    })
    
    probability = model.predict_proba(data)[0][1]
    
    THRESHOLD = 0.9
    
    if probability >= THRESHOLD:
        prediction = 1  
        risk_message = "ВЫСОКИЙ РИСК МОШЕННИЧЕСТВА!"
        recommendation = "Заблокировать транзакцию и связаться с клиентом"
    elif probability >= 0.4:
        prediction = 1  
        risk_message = "СРЕДНИЙ РИСК. Требуется подтверждение"
        recommendation = "Отправить СМС-код для подтверждения"
    else:
        prediction = 0  
        risk_message = "Низкий риск, транзакция безопасна"
        recommendation = "Транзакция может быть проведена"
    
    return {
        'is_fraud': bool(prediction),
        'probability': float(probability),
        'risk_message': risk_message,
        'recommendation': recommendation,
        'threshold_used': THRESHOLD
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Бот для обнаружения мошенничества. Верный помощник банков.*\n\n"
        "Я помогу определить, является ли транзакция мошеннической.\n\n"
        "*Как использовать:*\n"
        "Отправьте 8 чисел через запятую:\n"
        "`сумма, население, широта локации клиента, долгота локации клиента, широта локации (магазина), долгота локации (магазина), час, расстояние`\n\n"
        "*Пример:*\n"
        "`100.5, 500000, 40.7128, -74.0060, 40.7580, -73.9855, 14, 5.2`\n\n"
        "*Команды:*\n"
        "/start - Показать это меню\n"
        "/help - Подробная инструкция\n",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Как пользоваться ботом — простая инструкция*\n\n"
        
        "??? *Что нужно сделать:*\n\n"
        "Просто отправьте боту 8 чисел через запятую в таком порядке:\n\n"
        
        "1. *Сумма покупки* — сколько потратили (например: 1500.50)\n"
        "2. *Население города* — где живёт покупатель (например: 500000)\n"
        "3. *Где находится покупатель* — широта (например: 55.7512)\n"
        "4. *Где находится покупатель* — долгота (например: 37.6184)\n"
        "5. *Где находится магазин* — широта (например: 55.7300)\n"
        "6. *Где находится магазин* — долгота (например: 37.6400)\n"
        "7. *Время покупки* — час от 0 до 23 (например: 14)\n"
        "8. *Расстояние* от покупателя до магазина в км (например: 3.5)\n\n"
        
        
        "*Пример готового сообщения:*\n"
        "`1500.50, 500000, 55.7512, 37.6184, 55.7300, 37.6400, 14, 3.5`\n\n"
        
        "Это значит: покупка на 1500 рублей в Москве, покупатель в центре, магазин в 3.5 км, днём в 14 часов\n\n"
        
        "*Важные правила:*\n\n"
        "Пишите числа через запятую, в одной строке\n"
        "Дробные числа пишите через точку, а не запятую (например: 10.5, а не 10,5)\n"
        "Час должен быть от 0 (полночь) до 23 (11 вечера)\n"
        "Расстояние — это километры между вами и магазином\n\n"
        
        
        "*Что будет после отправки?*\n\n"
        "Бот проанализирует транзакцию и скажет:\n"
        "Безопасно — можно проводить платеж\n"
        "МОШЕННИЧЕСТВО — лучше заблокировать\n"
        "Предложит отправить смс-подтверждение для проверки\n"
        "А также покажет вероятность мошенничества в %\n\n"
        
        
        "*Где взять все эти данные?*\n\n"
        "Сумма, время, местоположение — из информации о транзакции\n"
        "Расстояние можно посчитать в навигаторе или картах\n"
        "Если не знаете точные координаты — используйте примерные\n\n"
        
        "*Команды помощника:*\n"
        "/start — показать приветствие\n"
        "/help — эта инструкция\n",
        
        parse_mode='Markdown'
    )



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        values = [float(x.strip()) for x in text.split(',')]
        if len(values) != 8:
            await update.message.reply_text(
                f"!!! *Ошибка:* нужно 8 чисел, вы ввели {len(values)}\n\n"
                f"*Правильный формат:*\n"
                f"`сумма, население, широта_клиента, долгота_клиента, широта_магазина, долгота_магазина, час, расстояние`\n\n"
                f"*Пример:*\n"
                f"`100.5, 500000, 40.7128, -74.0060, 40.7580, -73.9855, 14, 5.2`",
                parse_mode='Markdown'
            )
            return
        
        amount, city_pop, lat, lon, merch_lat, merch_long, hour, distance_km = values
        
        if hour < 0 or hour > 23:
            await update.message.reply_text("Час должен быть от 0 до 23")
            return
        
        if distance_km < 0:
            await update.message.reply_text("Расстояние не может быть отрицательным")
            return
        
        result = predict_fraud(amount, city_pop, lat, lon, merch_lat, merch_long, hour, distance_km)
        
        log_to_postgres(
            user_id=user_id,
            amount=amount,
            city_pop=city_pop,
            lat=lat,
            lon=lon,
            merch_lat=merch_lat,
            merch_long=merch_long,
            hour=hour,
            distance_km=distance_km,
            is_fraud=result['is_fraud'],
            probability=result['probability'],
            risk_message=result['risk_message']
        )
        
        response = (
            f"{result['risk_message']}\n\n"
            f"*Вероятность мошенничества:* {result['probability']*100:.1f}%\n\n"
            f"*Проверенные данные:*\n"
            f"   Сумма: ${amount:.2f}\n"
            f"   Час: {hour:.0f}:00\n"
            f"   Расстояние: {distance_km:.1f} км"
        )
        
        if result['is_fraud']:
            response += "\n\n*Рекомендация:* Заблокировать транзакцию и связаться с клиентом"
        else:
            response += "\n\n*Рекомендация:* Транзакция может быть проведена"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text(
            "*Ошибка:* неверный формат чисел\n\n"
            "Убедитесь, что используете **точку** (.), а не запятую для дробных чисел\n\n"
            "*Пример:*\n"
            "`100.5, 500000, 40.7128, -74.0060, 40.7580, -73.9855, 14, 5.2`",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")


if __name__ == "__main__":
    if model and TELEGRAM_TOKEN:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("Бот запущен! Напишите /start в Telegram")
        app.run_polling()
    else:
        print("Укажите токен и проверьте модель")
        

