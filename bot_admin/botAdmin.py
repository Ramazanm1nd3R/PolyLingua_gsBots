import telebot
from telebot import types
import psycopg2

ADMIN_ID = ADMINISTRATOR TG ID  # ID администратора


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
bot_token = 'teleg_token'
bot = telebot.TeleBot(bot_token)

# Состояния для обработки пошагового добавления/редактирования курса
ADD_COURSE, EDIT_COURSE = range(2)

# Словарь для временного хранения данных о курсах
course_data = {}


@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(row_width=2)
        btn_add = types.KeyboardButton("Добавить курс")
        btn_edit = types.KeyboardButton("Редактировать курс")
        markup.add(btn_add, btn_edit)
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "У вас нет доступа к этому боту.")


@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.text in ["Добавить курс", "Редактировать курс"])
def handle_course_actions(message):
    if message.text == "Добавить курс":
        add_course(message)
    elif message.text == "Редактировать курс":
        edit_course(message)


def add_course(message):
    bot.send_message(message.chat.id, "Введите название курса:")
    bot.register_next_step_handler(message, get_course_name, ADD_COURSE)


def get_course_name(message, action):
    course_data[message.chat.id] = {'name': message.text}
    bot.send_message(message.chat.id, "Введите описание курса:")
    bot.register_next_step_handler(message, get_course_description, action)


def get_course_description(message, action):
    course_data[message.chat.id]['description'] = message.text
    bot.send_message(message.chat.id, "Введите цену курса:")
    bot.register_next_step_handler(message, get_course_price, action)


def get_course_price(message, action):
    try:
        price = float(message.text)
        course_data[message.chat.id]['price'] = price
        bot.send_message(message.chat.id, "Загрузите изображение для курса:")
        bot.register_next_step_handler(message, get_course_image, action)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите правильную цену.")
        bot.register_next_step_handler(message, get_course_price, action)


def get_course_image(message, action):
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        image_data = bot.download_file(file_path)
        image_id = save_image_to_db(image_data)
        course_data[message.chat.id]['image_id'] = image_id
        save_course_to_db(message.chat.id, action)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, загрузите изображение.")
        bot.register_next_step_handler(message, get_course_image, action)


def save_image_to_db(image_data):
    conn = create_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO course_images (image) VALUES (%s) RETURNING image_id", (psycopg2.Binary(image_data),))
        image_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return image_id
    except Exception as e:
        print(f"Ошибка при сохранении изображения: {e}")
        return None


def save_course_to_db(chat_id, action):
    conn = create_connection()
    if not conn:
        bot.send_message(chat_id, "Ошибка подключения к базе данных.")
        return
    data = course_data[chat_id]
    try:
        cursor = conn.cursor()
        if action == ADD_COURSE:
            cursor.execute("INSERT INTO courses (course_name, course_description, course_price, image_id) VALUES (%s, %s, %s, %s)", (data['name'], data['description'], data['price'], data['image_id']))
            bot.send_message(chat_id, "Курс успешно добавлен в базу данных.")
        elif action == EDIT_COURSE:
            cursor.execute("UPDATE courses SET course_name = %s, course_description = %s, course_price = %s, image_id = %s WHERE course_id = %s", (data['name'], data['description'], data['price'], data['image_id'], data['course_id']))
            bot.send_message(chat_id, "Курс успешно обновлен в базу данных.")
        conn.commit()
        cursor.close()
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при сохранении в базу данных: {e}")
    finally:
        conn.close()


def edit_course(message):
    bot.send_message(message.chat.id, "Введите название курса, который хотите отредактировать:")
    bot.register_next_step_handler(message, get_course_info_for_edit)


def get_course_info_for_edit(message):
    course_name = message.text
    if course_name.strip().lower() == "скип":
        start(message)
    else:
        course_info = find_course_by_name(course_name)
        if course_info:
            course_data[message.chat.id] = {
                'course_id': course_info[0],
                'name': course_info[1],
                'description': course_info[2],
                'price': course_info[3],
                'image_id': course_info[4]
            }
            bot.send_message(message.chat.id, "Введите новое название курса (или отправьте 'скип', если не хотите менять):")
            bot.register_next_step_handler(message, get_new_course_info_for_edit)
        else:
            bot.send_message(message.chat.id, "Курс с таким названием не найден.")
            start(message)


def get_new_course_info_for_edit(message):
    action = EDIT_COURSE
    new_name = message.text.strip()
    if new_name.lower() == "скип":
        bot.send_message(message.chat.id, "Название курса не будет изменено. Введите новое описание курса (или отправьте 'скип', если не хотите менять):")
        bot.register_next_step_handler(message, get_new_course_description_for_edit, action)
    else:
        course_data[message.chat.id]['name'] = new_name
        bot.send_message(message.chat.id, "Введите новое описание курса (или отправьте 'скип', если не хотите менять):")
        bot.register_next_step_handler(message, get_new_course_description_for_edit, action)


def get_new_course_description_for_edit(message, action):
    new_description = message.text.strip()
    if new_description.lower() == "скип":
        bot.send_message(message.chat.id, "Описание курса не будет изменено. Введите новую цену курса (или отправьте 'скип', если не хотите менять):")
        bot.register_next_step_handler(message, get_new_course_price_for_edit, action)
    else:
        course_data[message.chat.id]['description'] = new_description
        bot.send_message(message.chat.id, "Введите новую цену курса (или отправьте 'скип', если не хотите менять):")
        bot.register_next_step_handler(message, get_new_course_price_for_edit, action)


def get_new_course_price_for_edit(message, action):
    new_price = message.text.strip()
    if new_price.lower() == "скип":
        bot.send_message(message.chat.id, "Цена курса не будет изменена. Загрузите новое изображение для курса (или отправьте 'скип', если не хотите менять):")
        bot.register_next_step_handler(message, get_new_course_image_for_edit, action)
    else:
        try:
            price = float(new_price)
            course_data[message.chat.id]['price'] = price
            bot.send_message(message.chat.id, "Загрузите новое изображение для курса (или отправьте 'скип', если не хотите менять):")
            bot.register_next_step_handler(message, get_new_course_image_for_edit, action)
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите правильную цену.")
            bot.register_next_step_handler(message, get_new_course_price_for_edit, action)


def get_new_course_image_for_edit(message, action):
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path

        # Загрузка изображения
        image_data = bot.download_file(file_path)

        image_id = save_image_to_db(image_data)

        course_data[message.chat.id]['image_id'] = image_id

        update_course_in_db(message.chat.id)
    else:
        update_course_in_db(message.chat.id)


def find_course_by_name(name):
    conn = create_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT course_id, course_name, course_description, course_price, image_id
            FROM courses
            WHERE course_name ILIKE %s
            """,
            (name,)
        )
        course_info = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return course_info
    except Exception as e:
        print(f"Ошибка при поиске информации о курсе: {e}")
        return None


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
            (data['name'], data['description'], data['price'], data['image_id'], data['course_id'])
        )
        conn.commit()
        cursor.close()
        conn.close()
        bot.send_message(chat_id, "Курс успешно обновлен в базе данных.")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении базы данных: {e}")


# Запуск бота
bot.polling()
