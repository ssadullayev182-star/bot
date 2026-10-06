import io
import telebot
from PIL import Image
from rembg import new_session, remove
from telebot import types

TOKEN = "8210723756:AAFRy1DFu-tkeScOaAASwJtF95KdEmlt09M"

bot = telebot.TeleBot(TOKEN)
bot_session = new_session("u2net")

# Словари для хранения данных и состояний пользователей
user_original_photos = {}
user_bg_custom_photos = {}  # Для хранения картинки, которая пойдет на фон
user_states = {}


# Главное меню
def get_main_menu():
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  btn1 = types.KeyboardButton("✂️ Удалить фон")
  btn2 = types.KeyboardButton("✍️ Создать текст")
  markup.add(btn1, btn2)
  return markup


@bot.message_handler(commands=["start"])
def send_welcome(message):
  chat_id = message.chat.id
  user_states[chat_id] = None
  bot.send_message(
      chat_id,
      f"Привет, {message.from_user.first_name}! 👋\nЯ многофункциональный бот."
      " Выбери нужное действие в меню ниже:",
      reply_markup=get_main_menu(),
  )


# Обработка кнопок главного меню
@bot.message_handler(
    func=lambda message: message.text in ["✂️ Удалить фон", "✍️ Создать текст"]
)
def handle_menu_buttons(message):
  chat_id = message.chat.id
  text = message.text

  if text == "✂️ Удалить фон":
    user_states[chat_id] = "waiting_for_photo"
    bot.send_message(
        chat_id,
        "📸 Отправь мне фотографию, а я удалю с неё фон!",
        reply_markup=get_main_menu(),
    )

  elif text == "✍️ Создать текст":
    user_states[chat_id] = "waiting_for_essay_topic"
    bot.send_message(
        chat_id,
        "✍️ Введите тему для эссе или сочинения, и я напишу его на английском и"
        " русском языках:",
        reply_markup=get_main_menu(),
    )


# Обработчик входящих фотографий
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
  chat_id = message.chat.id
  state = user_states.get(chat_id)

  # 1. Если ждем фото для удаления фона
  if state == "waiting_for_photo":
    try:
      processing_msg = bot.reply_to(
          message, "⏳ Обрабатываю фото, удаляю фон..."
      )

      file_info = bot.get_file(message.photo[-1].file_id)
      downloaded_file = bot.download_file(file_info.file_path)

      user_original_photos[chat_id] = downloaded_file
      user_states[chat_id] = "choosing_bg_method"

      output_data = remove(downloaded_file, session=bot_session)
      output_image = io.BytesIO(output_data)
      output_image.name = "no_bg.png"

      # Две инлайн-кнопки под документом
      markup = types.InlineKeyboardMarkup()
      btn_color_bg = types.InlineKeyboardButton(
          "🎨 Цвет фона", callback_data="bg_color"
      )
      btn_image_bg = types.InlineKeyboardButton(
          "🖼️ Своя картинка для фона", callback_data="bg_image"
      )
      markup.add(btn_color_bg, btn_image_bg)

      bot.send_document(
          chat_id,
          output_image,
          caption=(
              "Готово! Выберите способ замены фона с помощью кнопок ниже:"
          ),
          reply_markup=markup,
      )
      bot.delete_message(chat_id, processing_msg.message_id)

    except Exception as e:
      bot.reply_to(message, f"Ой, произошла ошибка при обработке фото: {e}")

  # 2. Если мы находимся в режиме ожидания картинки ДЛЯ ФОНА
  elif state == "waiting_for_bg_image":
    try:
      processing_msg = bot.reply_to(
          message, "⏳ Накладываю объект на вашу картинку-фон..."
      )

      # Скачиваем присланную картинку для фона
      file_info = bot.get_file(message.photo[-1].file_id)
      bg_file_bytes = bot.download_file(file_info.file_path)

      # Вырезаем объект из оригинала
      no_bg_bytes = remove(
          user_original_photos[chat_id], session=bot_session
      )
      foreground = Image.open(io.BytesIO(no_bg_bytes)).convert("RGBA")

      # Открываем фоновую картинку и подгоняем под размер переднего плана
      background = Image.open(io.BytesIO(bg_file_bytes)).convert("RGBA")
      background = background.resize(foreground.size, Image.Resampling.LANCZOS)

      # Соединяем
      combined = Image.alpha_composite(background, foreground)

      final_image = combined.convert("RGB")
      output_io = io.BytesIO()
      final_image.save(output_io, format="JPEG", quality=95)
      output_io.seek(0)

      bot.send_photo(
          chat_id, output_io, caption="✨ Готово! Фон успешно заменен на фото."
      )
      bot.delete_message(chat_id, processing_msg.message_id)

      user_states[chat_id] = None

    except Exception as e:
      bot.reply_to(
          message,
          f"Ошибка при наложении фона: {e}",
          reply_markup=get_main_menu(),
      )
      user_states[chat_id] = None
  else:
    bot.reply_to(
        message,
        "Пожалуйста, используйте кнопки меню 👇",
        reply_markup=get_main_menu(),
    )


# Обработка инлайн-кнопок выбора типа фона
@bot.callback_query_handler(
    func=lambda call: call.data in ["bg_color", "bg_image"]
)
def callback_bg_choice(call):
  chat_id = call.message.chat.id

  if chat_id not in user_original_photos:
    bot.answer_callback_query(call.id, "Сначала отправьте фотографию!")
    return

  bot.answer_callback_query(call.id)

  if call.data == "bg_color":
    user_states[chat_id] = "changing_bg_color"
    bot.send_message(
        chat_id,
        "✍️ Напишите цвет фона на английском языке (например: *red*, *blue*,"
        " *black* или HEX-код *#ff0000*):",
        parse_mode="Markdown",
    )
  elif call.data == "bg_image":
    user_states[chat_id] = "waiting_for_bg_image"
    bot.send_message(
        chat_id,
        "🖼️ Отправьте мне **вторую фотографию**, которую хотите сделать"
        " фоном:",
        parse_mode="Markdown",
    )


# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_text(message):
  chat_id = message.chat.id
  state = user_states.get(chat_id)

  # Смена фона цветом
  if state == "changing_bg_color":
    bg_color = message.text.strip().lower()

    if chat_id not in user_original_photos:
      bot.reply_to(
          message,
          "Сначала отправьте фотографию.",
          reply_markup=get_main_menu(),
      )
      user_states[chat_id] = None
      return

    try:
      processing_msg = bot.reply_to(message, f"🎨 Меняю фон на «{bg_color}»...")

      no_bg_bytes = remove(
          user_original_photos[chat_id], session=bot_session
      )
      foreground = Image.open(io.BytesIO(no_bg_bytes)).convert("RGBA")

      width, height = foreground.size
      background = Image.new("RGBA", (width, height), bg_color)
      combined = Image.alpha_composite(background, foreground)

      final_image = combined.convert("RGB")
      output_io = io.BytesIO()
      final_image.save(output_io, format="JPEG", quality=95)
      output_io.seek(0)

      bot.send_photo(
          chat_id, output_io, caption=f"✨ Готово! Новый фон: {bg_color}"
      )
      bot.delete_message(chat_id, processing_msg.message_id)
      user_states[chat_id] = None

    except Exception as e:
      bot.reply_to(
          message,
          f"Не удалось установить цвет («{bg_color}»). Проверьте правильность"
          " написания.",
          reply_markup=get_main_menu(),
      )
      user_states[chat_id] = None

  # Генерация эссе (сочинения) на англ и русс
  elif state == "waiting_for_essay_topic":
    topic = message.text.strip()
    processing_msg = bot.reply_to(
        message, f"📖 Пишу сочинение на тему: «{topic}»..."
    )

    # Простая заготовка сгенерированного текста (здесь можно подключить ИИ-модель, если захотите)
    essay_en = (
        f"<b>English Essay: The Importance of {topic}</b>\n\n{topic} plays a"
        " crucial role in our modern world. It impacts our daily lives,"
        " perspectives, and future developments. Understanding this concept"
        " allows us to explore new opportunities and solve complex challenges"
        " effectively. In conclusion, {topic} remains a vital subject of"
        " discussion and continuous growth."
    )

    essay_ru = (
        f"<b>Сочинение на русском: Важность темы «{topic}»</b>\n\n{topic} играет"
        " ключевую роль в нашем современном мире. Это явление влияет на нашу"
        " повседневную жизнь, взгляды и дальнейшее развитие. Понимание данной"
        " концепции открывает новые возможности и помогает эффективно решать"
        " сложные задачи. В заключение можно сказать, что {topic} остается"
        " важным предметом для обсуждения и постоянного совершенствования."
    )

    bot.send_message(chat_id, essay_en, parse_mode="HTML")
    bot.send_message(chat_id, essay_ru, parse_mode="HTML")
    bot.delete_message(chat_id, processing_msg.message_id)

    user_states[chat_id] = None

  else:
    bot.reply_to(
        message,
        "Пожалуйста, выберите нужный пункт меню с помощью кнопок внизу 👇",
        reply_markup=get_main_menu(),
    )


if __name__ == "__main__":
  print("Многофункциональный бот запущен и готов к работе...")
  bot.infinity_polling()