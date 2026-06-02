import os
import joblib
import pandas as pd
import numpy as np
import psycopg2
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


NEW_TOKEN = "8884482898:AAHYonhJAAno9cXFMT4fPiamnfGFx3njXXI"
MODEL_PATH = "ensemble_my_models.pkl"


DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "fraud_db")
DB_USER = os.getenv("POSTGRES_USER", "fraud_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "fraud_pass")


try:
    model = joblib.load(MODEL_PATH)
    print("Модель загружена")
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    model = None

def save_to_postgres(user_id, amount, city_pop, lat, lon, merch_lat, merch_long, 
                     hour, distance_km, is_fraud, probability):
    try:
        amount = float(amount)
        city_pop = float(city_pop)
        lat = float(lat)
        lon = float(lon)
        merch_lat = float(merch_lat)
        merch_long = float(merch_long)
        hour = int(hour)
        distance_km = float(distance_km)
        probability = float(probability)
        
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
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
                probability FLOAT
            )
        """)
        
        cur.execute("""
            INSERT INTO prediction_logs 
            (user_id, amount, city_pop, lat, lon, merch_lat, merch_long, 
             hour, distance_km, is_fraud, probability)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (str(user_id), amount, city_pop, lat, lon, merch_lat, merch_long, 
              hour, distance_km, is_fraud, probability))
        
        conn.commit()
        cur.close()
        conn.close()
        print("Сохранено в PostgreSQL")
    except Exception as e:
        print(f"Ошибка PostgreSQL: {e}")
        
        cur.execute("""
            INSERT INTO prediction_logs 
            (user_id, amount, city_pop, lat, lon, merch_lat, merch_long, 
             hour, distance_km, is_fraud, probability)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (str(user_id), amount, city_pop, lat, lon, merch_lat, merch_long, 
              hour, distance_km, is_fraud, probability))
        
        conn.commit()
        cur.close()
        conn.close()
        print("Сохранено в PostgreSQL")
    except Exception as e:
        print(f"Ошибка PostgreSQL: {e}")

def predict_fraud(amount, city_pop, lat, lon, merch_lat, merch_long, hour, distance_km):
    data = pd.DataFrame([{
        'amt': amount, 'city_pop': city_pop, 'lat': lat, 'long': lon,
        'merch_lat': merch_lat, 'merch_long': merch_long, 'hour': hour, 'distance_km': distance_km
    }])
    probability = model.predict_proba(data)[0][1]
    
    if probability >= 0.9:
        risk = "ВЫСОКИЙ РИСК!"
        rec = "Заблокировать транзакцию"
        is_fraud = True
    elif probability >= 0.3:
        risk = "СРЕДНИЙ РИСК"
        rec = "Отправить СМС-код для подтверждения"
        is_fraud = True
    else:
        risk = "НИЗКИЙ РИСК"
        rec = "Транзакция может быть проведена"
        is_fraud = False
    
    return {
        'is_fraud': is_fraud,
        'probability': probability,
        'risk_message': risk,
        'recommendation': rec
    }

async def start(update: Update, context):
    await update.message.reply_text(
        "*Бот для обнаружения мошенничества*\n\n"
        "Я помогаю банкам определить, является ли транзакция мошеннической.\n\n"
        "*Как использовать:*\n"
        "Отправьте 8 чисел через запятую:\n"
        "`сумма, население, широта_клиента, долгота_клиента, широта_магазина, долгота_магазина, час, расстояние`\n\n"
        "*Пример:*\n"
        "`100.5, 500000, 40.7128, -74.0060, 40.7580, -73.9855, 14, 5.2`\n\n"
        "*Команды:*\n"
        "/start - Показать это меню\n"
        "/help - Подробная инструкция\n"
        "/stats - Статистика проверок",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context):
    await update.message.reply_text(
        "*Подробная инструкция*\n\n"
        "*Что нужно отправить:*\n"
        "1. *Сумма* — сколько потратили (например: 1500.50)\n"
        "2. *Население города* клиента (например: 500000)\n"
        "3. *Широта* клиента (например: 55.7512)\n"
        "4. *Долгота* клиента (например: 37.6184)\n"
        "5. *Широта* магазина (например: 55.7300)\n"
        "6. *Долгота* магазина (например: 37.6400)\n"
        "7. *Час* покупки (от 0 до 23)\n"
        "8. *Расстояние* до магазина в км (например: 3.5)\n\n"
        "*Правила:*\n"
        "• Числа через запятую, в одной строке\n"
        "• Дробные числа через точку (10.5, а не 10,5)\n"
        "• Час от 0 (полночь) до 23 (11 вечера)\n\n"
        "*Пример правильного сообщения:*\n"
        "`1500.50, 500000, 55.7512, 37.6184, 55.7300, 37.6400, 14, 3.5`\n\n"
        "*Что вы получите:*\n"
        "• Оценку риска (высокий/средний/низкий)\n"
        "• Вероятность мошенничества в %\n"
        "• Рекомендацию по транзакции\n\n"
        "*Команды:*\n"
        "/start — Главное меню\n"
        "/help — Эта инструкция\n"
        "/stats — Статистика проверок",
        parse_mode='Markdown'
    )

async def stats_command(update: Update, context):
    user_id = update.effective_user.id
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Статистика пользователя
        cur.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_fraud = true THEN 1 ELSE 0 END) as frauds
            FROM prediction_logs 
            WHERE user_id = %s
        """, (str(user_id),))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        total = result[0] or 0
        frauds = result[1] or 0
        
        await update.message.reply_text(
            f"*Ваша статистика*\n\n"
            f"Всего проверок: `{total}`\n"
            f"Выявлено рисков: `{frauds}`\n"
            f"Процент рисков: `{frauds/total*100:.1f}%`" if total > 0 else "Пока нет проверок",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"Статистика временно недоступна")

async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        values = [float(x.strip()) for x in text.split(',')]
        if len(values) != 8:
            await update.message.reply_text(
                "❌ *Ошибка:* нужно 8 чисел\n\n"
                "📌 *Пример:*\n"
                "`100.5, 500000, 40.7128, -74.0060, 40.7580, -73.9855, 14, 5.2`\n\n"
                "📖 Подробнее: /help",
                parse_mode='Markdown'
            )
            return
        
        amount, city_pop, lat, lon, merch_lat, merch_long, hour, distance_km = values
        
        if hour < 0 or hour > 23:
            await update.message.reply_text("Час должен быть от 0 до 23")
            return
        
        result = predict_fraud(amount, city_pop, lat, lon, merch_lat, merch_long, hour, distance_km)
        
        # Сохраняем в PostgreSQL
        save_to_postgres(user_id, amount, city_pop, lat, lon, merch_lat, merch_long, 
                         hour, distance_km, result['is_fraud'], result['probability'])
        
        response = (
            f"{result['risk_message']}\n\n"
            f"*Вероятность мошенничества:* `{result['probability']*100:.1f}%`\n\n"
            f"*Рекомендация:* {result['recommendation']}"
        )
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text(
            "*Ошибка:* неверный формат чисел\n\n"
            "Используйте **точку** (.) для дробных чисел\n\n"
            "*Пример:* `100.5, 500000, 40.7128, -74.0060, 40.7580, -73.9855, 14, 5.2`\n\n"
            "Подробнее: /help",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

if __name__ == "__main__":
    if model and NEW_TOKEN:
        app = Application.builder().token(NEW_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("Бот запущен!")
        print("Доступные команды: /start, /help, /stats")
        app.run_polling()
    else:
        print("❌ Ошибка: модель или токен не найдены")
