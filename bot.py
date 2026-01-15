import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from dotenv import load_dotenv
from receipt_processor import ReceiptProcessor
from qr_parser import parse_fns_url
import tempfile

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация процессора чеков
processor = ReceiptProcessor()

# Хранилище временных данных (в production использовать Redis/DB)
pending_receipts = {}

# Хранилище для media groups (альбомов)
media_groups = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start
    """
    await update.message.reply_text(
        "👋 Привет! Я бот для обработки чеков самозанятых.\n\n"
        "📤 Отправь мне:\n"
        "• 📸 Фото чека (или несколько сразу)\n"
        "• 📄 PDF файл\n"
        "• 🔗 Ссылку на чек ФНС\n\n"
        "Я распознаю данные и загружу чек на Google Drive + добавлю в таблицу."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка фото чека (включая альбомы)
    """
    message = update.message
    photo = message.photo[-1]
    
    # Проверяем, это одиночное фото или альбом
    if message.media_group_id:
        # Это часть альбома
        media_group_id = message.media_group_id
        
        # Инициализируем группу, если её еще нет
        if media_group_id not in media_groups:
            media_groups[media_group_id] = {
                'photos': [],
                'user_id': update.effective_user.id,
                'chat_id': message.chat_id,
                'notified': False,
                'processing': False
            }
        
        # Добавляем фото в группу
        media_groups[media_group_id]['photos'].append(photo)
        
        # Отправляем уведомление только один раз
        if not media_groups[media_group_id]['notified']:
            await message.reply_text(
                f"📸 Получаю альбом из фото...\n"
                f"Жду все фото, затем начну обработку."
            )
            media_groups[media_group_id]['notified'] = True
        
        # Запускаем обработку в фоне (если еще не запущена)
        if not media_groups[media_group_id]['processing']:
            media_groups[media_group_id]['processing'] = True
            # Используем asyncio.create_task вместо JobQueue
            import asyncio
            asyncio.create_task(
                process_media_group_delayed(
                    context,
                    media_group_id,
                    message.chat_id
                )
            )
    else:
        # Одиночное фото
        await update.message.reply_text("⏳ Обрабатываю чек...")
        await process_single_photo(update, photo)


async def process_single_photo(update: Update, photo):
    """
    Обработка одного фото
    """
    try:
        # Скачиваем фото
        photo_file = await photo.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            await photo_file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Обрабатываем чек
        success, data, message = processor.process_receipt_image(tmp_path)
        
        if not success:
            await update.message.reply_text(
                f"❌ Ошибка обработки:\n{message}\n\n"
                f"Попробуй отправить более четкое фото."
            )
            os.unlink(tmp_path)
            return
        
        # Сохраняем данные для подтверждения
        user_id = update.effective_user.id
        pending_receipts[user_id] = {
            'data': data,
            'file_path': tmp_path
        }
        
        # Формируем сообщение с данными
        confirmation_text = format_receipt_data(data)
        
        # Кнопки подтверждения
        keyboard = [
            [
                InlineKeyboardButton("✅ Все верно", callback_data='confirm'),
                InlineKeyboardButton("✏️ Изменить", callback_data='edit')
            ],
            [InlineKeyboardButton("❌ Отменить", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка: {str(e)}"
        )


async def process_media_group_delayed(context, media_group_id, chat_id):
    """
    Отложенная обработка альбома (ждем 2 секунды, чтобы собрались все фото)
    """
    import asyncio
    await asyncio.sleep(2)
    
    # Проверяем, что группа существует
    if media_group_id not in media_groups:
        return
    
    group_info = media_groups[media_group_id]
    photos = group_info['photos']
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔄 Обрабатываю {len(photos)} чеков..."
    )
    
    results = []
    failed = []
    
    # Обрабатываем каждое фото
    for idx, photo in enumerate(photos, 1):
        try:
            # Скачиваем фото
            photo_file = await photo.get_file()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                await photo_file.download_to_drive(tmp_file.name)
                tmp_path = tmp_file.name
            
            # Обрабатываем чек
            success, data, message = processor.process_receipt_image(tmp_path)
            
            if success:
                # Сразу загружаем на Drive и в Sheets
                upload_success, upload_message = processor.upload_and_save(tmp_path, data)
                
                if upload_success:
                    results.append({
                        'num': idx,
                        'name': data.get('full_name'),
                        'amount': data.get('amount'),
                        'date': data.get('date')
                    })
                else:
                    failed.append(f"Чек {idx}: {upload_message}")
                
                os.unlink(tmp_path)
            else:
                failed.append(f"Чек {idx}: {message}")
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Ошибка обработки чека {idx}: {e}")
            failed.append(f"Чек {idx}: {str(e)}")
    
    # Формируем итоговое сообщение
    summary = f"✅ Обработано чеков: {len(results)}/{len(photos)}\n\n"
    
    if results:
        summary += "📋 <b>Успешно загружены:</b>\n"
        for r in results:
            summary += f"{r['num']}. {r['name']} - {r['amount']} ({r['date']})\n"
    
    if failed:
        summary += f"\n❌ <b>Ошибки ({len(failed)}):</b>\n"
        for f in failed:
            summary += f"• {f}\n"
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=summary,
        parse_mode='HTML'
    )
    
    # Удаляем группу из памяти
    del media_groups[media_group_id]


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка PDF документа
    """
    document = update.message.document
    
    # Проверяем, что это PDF
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text(
            "❌ Поддерживаются только PDF файлы.\n"
            "Отправь фото чека или PDF."
        )
        return
    
    await update.message.reply_text("⏳ Обрабатываю PDF...")
    
    try:
        # Скачиваем PDF
        file = await document.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            await file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Конвертируем PDF в изображение (первую страницу)
        from pdf2image import convert_from_path
        images = convert_from_path(tmp_path, first_page=1, last_page=1)
        
        if not images:
            await update.message.reply_text("❌ Не удалось прочитать PDF")
            os.unlink(tmp_path)
            return
        
        # Сохраняем как изображение
        img_path = tmp_path.replace('.pdf', '.jpg')
        images[0].save(img_path, 'JPEG')
        
        # Обрабатываем как изображение
        success, data, message = processor.process_receipt_image(img_path)
        
        if not success:
            await update.message.reply_text(
                f"❌ Ошибка обработки:\n{message}"
            )
            os.unlink(tmp_path)
            os.unlink(img_path)
            return
        
        # Сохраняем PDF (не jpg) для загрузки
        user_id = update.effective_user.id
        pending_receipts[user_id] = {
            'data': data,
            'file_path': tmp_path  # Сохраняем PDF
        }
        
        # Удаляем временное изображение
        os.unlink(img_path)
        
        # Подтверждение
        confirmation_text = format_receipt_data(data)
        keyboard = [
            [
                InlineKeyboardButton("✅ Все верно", callback_data='confirm'),
                InlineKeyboardButton("✏️ Изменить", callback_data='edit')
            ],
            [InlineKeyboardButton("❌ Отменить", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки PDF: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка: {str(e)}"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка текстовых сообщений (ссылок на чеки)
    """
    text = update.message.text
    
    # Проверяем, это ссылка на ФНС
    if 'lknpd.nalog.ru' in text or 'npd.nalog.ru' in text:
        await update.message.reply_text(
            "🔗 Получил ссылку на чек.\n\n"
            "⚠️ Для полной обработки отправь фото или PDF чека.\n"
            "По ссылке я не могу автоматически извлечь данные."
        )
        
        # Парсим URL
        url_data = parse_fns_url(text)
        if url_data:
            await update.message.reply_text(
                f"📋 Информация из ссылки:\n"
                f"ИНН продавца: {url_data.get('seller_inn', 'не найден')}\n"
                f"ID чека: {url_data.get('receipt_id', 'не найден')}\n\n"
                f"Отправь фото этого чека для полной обработки."
            )
    else:
        await update.message.reply_text(
            "❓ Не понял команду.\n\n"
            "Отправь:\n"
            "• 📸 Фото чека (можно несколько сразу)\n"
            "• 📄 PDF файл\n"
            "• 🔗 Ссылку на чек ФНС"
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка нажатий на кнопки
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    action = query.data
    
    # Проверяем, есть ли данные пользователя
    if user_id not in pending_receipts:
        await query.edit_message_text("❌ Данные устарели. Отправь чек заново.")
        return
    
    if action == 'confirm':
        # Подтверждение - загружаем на Drive и в Sheets
        await query.edit_message_text("⏳ Загружаю на Drive и в таблицу...")
        
        receipt_info = pending_receipts[user_id]
        data = receipt_info['data']
        file_path = receipt_info['file_path']
        
        try:
            # Загружаем и сохраняем
            success, result_message = processor.upload_and_save(file_path, data)
            
            if success:
                await query.edit_message_text(result_message, parse_mode='HTML')
            else:
                await query.edit_message_text(f"❌ Ошибка сохранения:\n{result_message}")
            
            # Удаляем временный файл
            os.unlink(file_path)
            del pending_receipts[user_id]
            
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)}")
    
    elif action == 'edit':
        await query.edit_message_text(
            "✏️ Для изменения данных отправь чек заново с более четким фото.\n\n"
            "Или используй команду для ручного ввода (в разработке)."
        )
        # Удаляем временные данные
        if user_id in pending_receipts:
            os.unlink(pending_receipts[user_id]['file_path'])
            del pending_receipts[user_id]
    
    elif action == 'cancel':
        await query.edit_message_text("❌ Обработка отменена.")
        # Удаляем временные данные
        if user_id in pending_receipts:
            os.unlink(pending_receipts[user_id]['file_path'])
            del pending_receipts[user_id]


def format_receipt_data(data):
    """
    Форматирование данных чека для отображения
    """
    fns_link = data.get('fns_url', '')
    
    # Используем HTML вместо Markdown
    return (
        "<b>📋 Распознанные данные:</b>\n\n"
        f"👤 ФИО: <code>{data.get('full_name', 'не найдено')}</code>\n"
        f"💰 Сумма: <code>{data.get('amount', 'не найдено')}</code>\n"
        f"📝 Услуги: <code>{data.get('services', 'не найдено')}</code>\n"
        f"🏢 ИНН покупателя: <code>{data.get('buyer_inn', 'не найден')}</code>\n"
        f"📅 Дата: <code>{data.get('date', 'не найдена')}</code>\n"
        f"✅ Статус: <code>{data.get('status', 'не найден')}</code>\n"
        f"🔗 <a href='{fns_link}'>Ссылка ФНС</a>\n\n"
        "Все верно?"
    )


def main():
    """
    Запуск бота
    """
    # Получаем токен из .env
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в .env")
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()