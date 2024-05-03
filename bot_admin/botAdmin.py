import telebot
from telebot import types
import psycopg2
from datetime import datetime


# Подключение к базе данных
def create_connection():
    try:
        conn = psycopg2.connect(
            dbname="baseName",
            user="postgres",
            password="password",
            host="localhost",
        )
        return conn
    except Exception as e:
        print("Ошибка подключения к базе данных: {}".format(e))
        return None


# Функция для сохранения информации о пользователе
def save_user_info(telegram_id, username):
    conn = create_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (telegram_id, username)
            VALUES (%s, %s)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            (telegram_id, username)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при сохранении пользователя в базу данных: {e}")


# Создаем бота
bot_token = 'teleg_token'  # Укажите токен вашего бота
bot = telebot.TeleBot(bot_token)

# Состояния для обработки пошагового добавления/редактирования курса
ADD_COURSE, EDIT_COURSE = range(2)

# Словарь для временного хранения данных о курсах
course_data = {}


# Функция для сохранения информации о пользователе при любом сообщении
@bot.message_handler(func=lambda message: True)
def track_user(message):
    save_user_info(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "Unknown"
    )

    if message.text == "Добавить курс":
        add_course(message)
    elif message.text == "Редактировать курс":
        edit_course(message)
    else:
        start(message)


# Начало добавления курса
def start(message):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    btn_add = types.KeyboardButton("Добавить курс")
    btn_edit = types.KeyboardButton("Редактировать курс")
    markup.add(btn_add, btn_edit)
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)


# Обработка кнопки добавления курса
def add_course(message):
    bot.send_message(message.chat.id, "Введите название курса:")
    bot.register_next_step_handler(message, get_course_name, ADD_COURSE)


# Получение названия курса
def get_course_name(message, action):
    course_data[message.chat.id] = {'name': message.text}
    bot.send_message(message.chat.id, "Введите описание курса:")
    bot.register_next_step_handler(message, get_course_description, action)


# Получение описания курса
def get_course_description(message, action):
    course_data[message.chat.id]['description'] = message.text
    bot.send_message(message.chat.id, "Введите цену курса:")
    bot.register_next_step_handler(message, get_course_price, action)


# Получение цены курса
def get_course_price(message, action):
    try:
        price = float(message.text)
        course_data[message.chat.id]['price'] = price
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите правильную цену.")
        bot.register_next_step_handler(message, get_course_price, action)
        return

    # Добавление шага для получения изображения
    bot.send_message(message.chat.id, "Загрузите изображение для курса:")
    bot.register_next_step_handler(message, get_course_image, action)


# Получение изображения курса
def get_course_image(message, action):
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path

        # Загрузка изображения
        image_data = bot.download_file(file_path)

        image_id = save_image_to_db(image_data)

        course_data[message.chat.id]['image_id'] = image_id

        if action == ADD_COURSE:
            save_course_to_db(message.chat.id)
            bot.send_message(message.chat.id, "Курс успешно добавлен в базу данных.")
        elif action == EDIT_COURSE:
            update_course_in_db(message.chat.id)
            bot.send_message(message.chat.id, "Курс успешно обновлен в базе данных.")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, загрузите изображение.")
        bot.register_next_step_handler(message, get_course_image, action)


# Сохранение изображения в базу данных
def save_image_to_db(image_data):
    conn = create_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO course_images (image)
            VALUES (%s)
            RETURNING image_id
            """,
            (psycopg2.Binary(image_data),)
        )
        image_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return image_id
    except Exception as e:
        print(f"Ошибка при сохранении изображения: {e}")
        return None


# Сохранение курса в базу данных
def save_course_to_db(chat_id):
    conn = create_connection()
    if not conn:
        bot.send_message(chat_id, "Ошибка подключения к базе данных.")
        return

    data = course_data[chat_id]

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO courses (course_name, course_description, course_price, image_id)
            VALUES (%s, %s, %s, %s)
            """,
            (data['name'], data['description'], data['price'], data['image_id'])
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при сохранении в базу данных: {e}")


# Обработка кнопки редактирования курса
@bot.message_handler(regexp="Редактировать курс")
def edit_course(message):
    bot.send_message(message.chat.id, "Введите ID курса, который хотите отредактировать:")
    bot.register_next_step_handler(message, get_course_id_for_edit)


# Получение ID курса для редактирования
def get_course_id_for_edit(message):
    try:
        course_id = int(message.text)
        course_data[message.chat.id] = {'course_id': course_id}
        bot.send_message(message.chat.id, "Введите новое название курса (или оставьте пустым, если не хотите менять):")
        bot.register_next_step_handler(message, get_course_name, EDIT_COURSE)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный ID.")
        bot.register_next_step_handler(message, get_course_id_for_edit)


# Обновление курса в базе данных
def update_course_in_db(chat_id):
    conn = create_connection()
    if not conn:
        bot.send_message(chat_id, "Ошибка подключения к базе данных.")
        return

    data = course_data[chat_id]

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE courses
            SET course_name = COALESCE(%s, course_name),
                course_description = COALESCE(%s, course_description),
                course_price = COALESCE(%s, course_price),
                image_id = COALESCE(%s, image_id)
            WHERE course_id = %s
            """,
            (data.get('name'), data['description'], data['price'], data['image_id'], data['course_id'])
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении базы данных: {e}")


# Запуск бота
bot.polling()
