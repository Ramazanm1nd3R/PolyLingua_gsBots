import telebot
import psycopg2
import logging

# Настройка логгера
logger = logging.getLogger("telebot")
logger.setLevel(logging.INFO)

# Настройка бота
TOKEN = 'teleg_token'
bot = telebot.TeleBot(TOKEN)


# Функция для подключения к базе данных
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
        logger.error("Ошибка подключения к базе данных: {}".format(e))
        return None


def send_image_to_user(chat_id, image_data, caption):
    try:
        bot.send_photo(chat_id, image_data, caption=caption)
    except Exception as e:
        print(f"Ошибка при отправке изображения: {e}")


# Функция для добавления пользователя в базу данных
def add_user(telegram_id, username):
    conn = create_connection()
    if conn is not None:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO users (telegram_id, username) VALUES (%s, %s)", (telegram_id, username))
            conn.commit()
        cur.close()
        conn.close()


# Функция для вывода информации о курсах
def list_courses(message):
    bot.send_message(message.chat.id, "Актуальные курсы:\n")
    conn = create_connection()
    if conn is not None:
        cur = conn.cursor()
        cur.execute("SELECT course_name, course_description, course_price, image_id FROM courses")
        courses = cur.fetchall()
        for course in courses:
            response = f"Название: {course[0]}\nОписание: {course[1]}\nЦена: {int(course[2])} тенге\n\n"
            image_data = get_image_from_db(course[3])
            send_image_to_user(message.chat.id, image_data, response)
        cur.close()
        conn.close()


# Функция для обработки команды /start
@bot.message_handler(commands=["start"])
def start(message):
    telegram_id = message.from_user.id
    username = message.from_user.username

    add_user(telegram_id, username)

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("О нас", "Информация о курсах", "Связь с нами")

    bot.send_message(message.chat.id, "Добро пожаловать! Выберите действие:", reply_markup=markup)


# Функция для обработки выбора пользователя
def process_option_selection(message):
    if message.text == "О нас":
        bot.send_message(message.chat.id, "Мы предлагаем качественные курсы. Узнайте больше на нашем сайте. Для выбора другого действия заново отправьте /start")
    elif message.text == "Информация о курсах":
        list_courses(message)  # Вызов функции для отображения курсов
    elif message.text == "Связь с нами":
        bot.send_message(message.chat.id, "Вы можете связаться с нами по электронной почте: example@example.com. Для выбора другого действия заново отправьте /start")


# Обработка выбора пользователя после нажатия кнопки
@bot.message_handler(content_types=["text"])
def handle_text_message(message):
    process_option_selection(message)


def get_image_from_db(image_id):
    try:
        with create_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT image
                    FROM course_images
                    WHERE image_id = %s
                    """,
                    (image_id,)
                )
                image_data = cursor.fetchone()[0]
                return image_data
    except Exception as e:
        print(f"Ошибка при получении изображения из базы данных: {e}")
        return None


# Запуск бота
bot.polling()
