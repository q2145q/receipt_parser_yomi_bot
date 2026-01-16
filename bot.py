import os
import logging
import tempfile
from datetime import datetime
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
from user_manager import UserManager
from drive_handler import DriveHandler
from analysis_handler import AnalysisSheetHandler
from statistics_handler import StatisticsHandler

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация менеджера пользователей
user_manager = UserManager()

# Инициализация сбора статистики
try:
    statistics = StatisticsHandler()
except Exception as e:
    logger.error(f"Ошибка инициализации статистики: {e}")
    statistics = None

# Хранилище структуры пользователей (chat_id -> user_structure)
user_structures = {}

# Хранилище для папок анализа (user_id -> folder_info)
analysis_folders = {}


def get_or_init_user_structure(chat_id, username=None, chat_title=None):
    """
    Получение или создание структуры папок/таблиц для пользователя
    Возвращает: {
        'user_folder_id': 'xxx',
        'user_folder_link': 'https://...',
        'user_sheet_id': 'xxx',
        'user_sheet_link': 'https://...',
        'chat_name': '@username' или 'Название чата'
    }
    """
    if chat_id in user_structures:
        return user_structures[chat_id]
    
    # Получаем имя чата
    chat_name = user_manager.get_chat_name(chat_id, username, chat_title)
    
    # Создаем или получаем структуру
    structure = user_manager.get_or_create_user_structure(chat_id, chat_name)
    structure['chat_name'] = chat_name
    
    # Сохраняем в памяти
    user_structures[chat_id] = structure
    
    logger.info(f"Инициализирована структура для {chat_name}: {structure}")
    
    return structure


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start
    """
    # Инициализируем пользователя
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    chat_title = update.effective_chat.title if update.effective_chat.type != 'private' else None
    
    structure = get_or_init_user_structure(chat_id, username, chat_title)
    
    # Логируем действие
    if statistics:
        statistics.log_action(
            user_id=chat_id,
            username=username,
            action="/start",
            result="успех",
            details=f"Инициализация структуры для {structure['chat_name']}"
        )
    
    await update.message.reply_text(
        "👋 Привет! Это ДЕМО-версия бота от команды YOMI\n\n"
        "🤖 Я помогаю обрабатывать чеки самозанятых:\n"
        "• Распознаю данные с фото\n"
        "• Загружаю на Google Drive\n"
        "• Добавляю в таблицу\n\n"
        "📤 Отправь мне:\n"
        "• 📸 Фото чека (или несколько сразу)\n"
        "• 📄 PDF файл\n"
        "• 🔗 Ссылку на чек ФНС\n"
        "• /full_analyze - массовая обработка из папки\n\n"
        f"📁 Твоя папка: {structure['user_folder_link']}\n"
        f"📊 Твоя таблица: {structure['user_sheet_link']}\n\n"
        "🚀 <b>Скоро:</b> автоматическая проверка актуальности чеков и другие улучшения!\n\n"
        "💰 Поддержать разработку: https://tbank.ru/cf/9wS7L6U5JP6\n"
        "💬 Предложения и вопросы: @mishaabramyan\n\n"
        "🎬 Другие продукты YOMI:\n"
        "• @yomi_invoice_bot - авансовые отчеты для кино\n"
        "• И многое другое → @yomicalendar",
        parse_mode='HTML'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /help - справка по боту
    """
    # Логируем действие
    if statistics:
        statistics.log_action(
            user_id=update.effective_chat.id,
            username=update.effective_user.username,
            action="/help",
            result="успех",
            details="Просмотр справки"
        )
    
    await update.message.reply_text(
        "📖 <b>Справка по боту YOMI</b>\n\n"
        "🤖 <b>Что я умею:</b>\n"
        "• Распознавать данные с чеков через AI\n"
        "• Загружать чеки на Google Drive\n"
        "• Добавлять данные в Google Sheets\n"
        "• Обрабатывать пачки чеков\n\n"
        "📤 <b>Как пользоваться:</b>\n"
        "1. Отправь фото чека или PDF\n"
        "2. Проверь распознанные данные\n"
        "3. Готово! Чек сохранен\n\n"
        "🔍 <b>Команды:</b>\n"
        "/start - главное меню\n"
        "/full_analyze - массовая обработка из папки\n"
        "/help - эта справка\n\n"
        "💡 <b>Советы:</b>\n"
        "• Фотографируй чеки при хорошем освещении\n"
        "• Можно отправлять несколько фото сразу\n"
        "• Для пачек чеков удобнее /full_analyze\n\n"
        "💰 Поддержать: https://tbank.ru/cf/9wS7L6U5JP6\n"
        "💬 Вопросы: @mishaabramyan\n"
        "🎬 Канал: @yomicalendar",
        parse_mode='HTML'
    )


async def full_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /full_analyze - массовая обработка чеков
    """
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    chat_title = update.effective_chat.title if update.effective_chat.type != 'private' else None
    
    # Инициализируем пользователя
    structure = get_or_init_user_structure(chat_id, username, chat_title)
    
    await update.message.reply_text("📁 Создаю папку для анализа...")
    
    try:
        # Логируем начало анализа
        if statistics:
            statistics.log_action(
                user_id=chat_id,
                username=username,
                action="/full_analyze - начало",
                result="успех",
                details=f"Создание папки для {structure['chat_name']}"
            )
        
        # Создаем папку с именем: @username ГГГГ-ММ-ДД ЧЧ-ММ
        timestamp = datetime.now().strftime("%Y-%m-%d %H-%M")
        folder_name = f"{structure['chat_name']} {timestamp}"
        
        # Создаем папку внутри папки пользователя
        drive = DriveHandler(structure['user_folder_id'])
        folder_id, folder_link = drive.create_analysis_folder(folder_name)
        
        # Сохраняем информацию о папке
        analysis_folders[chat_id] = {
            'folder_id': folder_id,
            'folder_name': folder_name,
            'folder_link': folder_link,
            'user_structure': structure
        }
        
        # Отправляем ссылку на папку с кнопкой
        keyboard = [
            [InlineKeyboardButton("🚀 Начать анализ", callback_data=f'analyze_{chat_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"✅ Папка создана!\n\n"
            f"📂 Название: {folder_name}\n"
            f"🔗 Ссылка: {folder_link}\n\n"
            f"📋 Инструкция:\n"
            f"1. Перейди по ссылке выше\n"
            f"2. Загрузи чеки (фото JPG/PNG или PDF)\n"
            f"3. Нажми кнопку \"Начать анализ\" ниже\n\n"
            f"⚠️ Убедись, что загрузил все нужные чеки перед началом анализа!"
        )
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Ошибка создания папки: {e}")
        
        # Логируем ошибку
        if statistics:
            statistics.log_action(
                user_id=chat_id,
                username=username,
                action="/full_analyze",
                result="ошибка",
                details=str(e)
            )
        
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатий на кнопки
    """
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Обработка кнопки "Начать анализ"
    if callback_data.startswith('analyze_'):
        chat_id = int(callback_data.split('_')[1])
        
        # Проверяем, что это тот же чат
        if chat_id != update.effective_chat.id:
            await query.edit_message_text("❌ Эта кнопка не для этого чата!")
            return
        
        # Проверяем, что папка существует
        if chat_id not in analysis_folders:
            await query.edit_message_text("❌ Папка не найдена. Создай новую через /full_analyze")
            return
        
        folder_info = analysis_folders[chat_id]
        
        await query.edit_message_text("🔄 Начинаю обработку чеков...\nЭто может занять несколько минут.")
        
        # Запускаем обработку
        await process_analysis_folder(query, folder_info)


async def process_analysis_folder(query, folder_info):
    """
    Обработка всех файлов из папки анализа
    """
    try:
        logger.info(f"Начало обработки папки: {folder_info}")
        
        folder_id = folder_info['folder_id']
        folder_name = folder_info['folder_name']
        folder_link = folder_info['folder_link']
        user_structure = folder_info['user_structure']
        
        # Получаем список файлов из папки
        drive = DriveHandler(user_structure['user_folder_id'])
        files = drive.list_files_in_folder(folder_id)
        
        logger.info(f"Найдено файлов: {len(files)}")
        
        if not files:
            await query.message.reply_text("❌ В папке нет файлов для обработки!")
            return
        
        await query.message.reply_text(f"📊 Найдено файлов: {len(files)}\nНачинаю обработку...")
        
        # Создаем таблицу для результатов анализа
        sheet_title = f"{folder_name}, анализ"
        analysis_sheet = AnalysisSheetHandler()
        spreadsheet_id, sheet_link = analysis_sheet.create_analysis_spreadsheet(sheet_title, folder_id)
        
        # Создаем процессор с пользовательской структурой
        processor = ReceiptProcessor(
            user_folder_id=user_structure['user_folder_id'],
            user_sheet_id=user_structure['user_sheet_id']
        )
        
        # Статистика
        total_files = len(files)
        processed_count = 0
        success_count = 0
        errors = []
        
        # Обрабатываем каждый файл
        for idx, file in enumerate(files, 1):
            try:
                file_id = file['id']
                file_name = file['name']
                file_type = file['mimeType']
                
                logger.info(f"Обработка файла {idx}/{total_files}: {file_name}")
                await query.message.reply_text(f"⏳ Обработка {idx}/{total_files}: {file_name}")
                
                # Скачиваем файл
                with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
                    tmp_path = tmp_file.name
                
                drive.download_file(file_id, tmp_path)
                
                # Если PDF - конвертируем в JPG
                if file_type == 'application/pdf':
                    from pdf2image import convert_from_path
                    images = convert_from_path(tmp_path, first_page=1, last_page=1)
                    
                    if not images:
                        errors.append(f"{file_name}: Не удалось прочитать PDF")
                        os.unlink(tmp_path)
                        continue
                    
                    # Сохраняем как изображение
                    img_path = tmp_path.replace('.tmp', '.jpg')
                    images[0].save(img_path, 'JPEG')
                    os.unlink(tmp_path)
                    tmp_path = img_path
                
                # Обрабатываем чек
                success, data, message = processor.process_receipt_image(tmp_path)
                
                if success:
                    # Добавляем ссылку на файл в Drive
                    file_link = f"https://drive.google.com/file/d/{file_id}/view"
                    data['drive_link'] = file_link
                    
                    # Добавляем в таблицу анализа
                    analysis_sheet.add_receipt_to_sheet(spreadsheet_id, data)
                    
                    # Добавляем в корневую таблицу пользователя с гиперссылкой на папку
                    processor.add_to_user_sheet(
                        data,
                        source_link=folder_link,
                        source_name=f"Папка: {folder_name}"
                    )
                    
                    # Обновляем статистику пользователя
                    if statistics:
                        statistics.update_user_stats(
                            user_id=query.message.chat_id,
                            username=query.from_user.username,
                            action_type='receipt',
                            success=True
                        )
                    
                    success_count += 1
                    processed_count += 1
                else:
                    errors.append(f"{file_name}: {message}")
                    processed_count += 1
                    
                    # Логируем ошибку в статистику
                    if statistics:
                        statistics.update_user_stats(
                            user_id=query.message.chat_id,
                            username=query.from_user.username,
                            action_type='receipt',
                            success=False
                        )
                
                # Удаляем временный файл
                os.unlink(tmp_path)
                
            except Exception as e:
                logger.error(f"Ошибка обработки файла {file_name}: {e}")
                errors.append(f"{file_name}: {str(e)}")
                processed_count += 1
        
        # Формируем итоговое сообщение
        result_message = f"✅ <b>Анализ завершен!</b>\n\n"
        result_message += f"📊 Обработано чеков: {processed_count}/{total_files}\n"
        result_message += f"✅ Успешно: {success_count}\n"
        result_message += f"❌ Ошибок: {len(errors)}\n\n"
        result_message += f"📁 Таблица анализа:\n{sheet_link}\n\n"
        result_message += f"📊 Корневая таблица:\n{user_structure['user_sheet_link']}\n\n"
        
        if errors:
            result_message += f"⚠️ <b>Список ошибок:</b>\n"
            for error in errors[:10]:  # Показываем первые 10 ошибок
                result_message += f"• {error}\n"
            
            if len(errors) > 10:
                result_message += f"\n... и еще {len(errors) - 10} ошибок"
        
        await query.message.reply_text(result_message, parse_mode='HTML')
        
        # Логируем завершение анализа
        if statistics:
            statistics.log_action(
                user_id=query.message.chat_id,
                username=query.from_user.username,
                action="/full_analyze - завершение",
                result="успех",
                details=f"Обработано: {success_count}/{total_files}"
            )
        
        # Удаляем информацию о папке из памяти
        chat_id = query.message.chat_id
        if chat_id in analysis_folders:
            del analysis_folders[chat_id]
        
    except Exception as e:
        logger.error(f"Ошибка обработки папки: {e}")
        await query.message.reply_text(f"❌ Произошла ошибка: {str(e)}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка каждого фото отдельно (без группировки)
    """
    message = update.message
    photo = message.photo[-1]
    
    # Инициализируем пользователя
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    chat_title = update.effective_chat.title if update.effective_chat.type != 'private' else None
    
    structure = get_or_init_user_structure(chat_id, username, chat_title)
    
    # Каждое фото обрабатываем независимо
    await message.reply_text("⏳ Обрабатываю чек...")
    
    try:
        # Скачиваем фото
        photo_file = await photo.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            await photo_file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Создаем процессор с пользовательской структурой
        processor = ReceiptProcessor(
            user_folder_id=structure['user_folder_id'],
            user_sheet_id=structure['user_sheet_id']
        )
        
        # Обрабатываем чек
        success, data, message_text = processor.process_receipt_image(tmp_path)
        
        if not success:
            await message.reply_text(
                f"❌ Ошибка обработки:\n{message_text}\n\n"
                f"Попробуй отправить более четкое фото."
            )
            os.unlink(tmp_path)
            return
        
        # Сразу загружаем без подтверждения
        upload_success, upload_message = processor.upload_and_save(tmp_path, data)
        
        if upload_success:
            # Обновляем статистику
            if statistics:
                statistics.update_user_stats(
                    user_id=chat_id,
                    username=username,
                    action_type='receipt',
                    success=True
                )
                statistics.log_action(
                    user_id=chat_id,
                    username=username,
                    action="Обработка фото",
                    result="успех",
                    details=f"ФИО: {data.get('full_name')}, Сумма: {data.get('amount')}"
                )
            
            # Успешно загружено
            error_info = ""
            if data.get('error_details'):
                error_info = f"\n\n⚠️ Ошибки распознавания:\n{data['error_details']}"
            
            summary = (
                f"✅ <b>Чек обработан!</b>\n\n"
                f"👤 {data.get('full_name')}\n"
                f"💰 {data.get('amount')}\n"
                f"📅 {data.get('date')}\n"
                f"📝 {data.get('services')}\n"
                f"📁 Загружено на Drive и в таблицу"
                f"{error_info}"
            )
            await message.reply_text(summary, parse_mode='HTML')
        else:
            # Логируем ошибку
            if statistics:
                statistics.update_user_stats(
                    user_id=chat_id,
                    username=username,
                    action_type='receipt',
                    success=False
                )
                statistics.log_action(
                    user_id=chat_id,
                    username=username,
                    action="Обработка фото",
                    result="ошибка",
                    details=upload_message
                )
            
            await message.reply_text(f"❌ Ошибка сохранения:\n{upload_message}")
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await message.reply_text(f"❌ Произошла ошибка: {str(e)}")


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
    
    # Инициализируем пользователя
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    chat_title = update.effective_chat.title if update.effective_chat.type != 'private' else None
    
    structure = get_or_init_user_structure(chat_id, username, chat_title)
    
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
        
        # Создаем процессор с пользовательской структурой
        processor = ReceiptProcessor(
            user_folder_id=structure['user_folder_id'],
            user_sheet_id=structure['user_sheet_id']
        )
        
        # Обрабатываем как изображение
        success, data, message_text = processor.process_receipt_image(img_path)
        
        if not success:
            await update.message.reply_text(
                f"❌ Ошибка обработки:\n{message_text}"
            )
            os.unlink(tmp_path)
            os.unlink(img_path)
            return
        
        # Удаляем временное изображение
        os.unlink(img_path)
        
        # Загружаем оригинальный PDF
        upload_success, upload_message = processor.upload_and_save(tmp_path, data)
        
        if upload_success:
            # Обновляем статистику
            if statistics:
                statistics.update_user_stats(
                    user_id=chat_id,
                    username=username,
                    action_type='receipt',
                    success=True
                )
                statistics.log_action(
                    user_id=chat_id,
                    username=username,
                    action="Обработка PDF",
                    result="успех",
                    details=f"ФИО: {data.get('full_name')}, Сумма: {data.get('amount')}"
                )
            
            error_info = ""
            if data.get('error_details'):
                error_info = f"\n\n⚠️ Ошибки распознавания:\n{data['error_details']}"
            
            summary = (
                f"✅ <b>Чек обработан!</b>\n\n"
                f"👤 {data.get('full_name')}\n"
                f"💰 {data.get('amount')}\n"
                f"📅 {data.get('date')}\n"
                f"📝 {data.get('services')}\n"
                f"📁 Загружено на Drive и в таблицу"
                f"{error_info}"
            )
            await update.message.reply_text(summary, parse_mode='HTML')
        else:
            # Логируем ошибку
            if statistics:
                statistics.update_user_stats(
                    user_id=chat_id,
                    username=username,
                    action_type='receipt',
                    success=False
                )
                statistics.log_action(
                    user_id=chat_id,
                    username=username,
                    action="Обработка PDF",
                    result="ошибка",
                    details=upload_message
                )
            
            await update.message.reply_text(f"❌ Ошибка сохранения:\n{upload_message}")
        
        # Удаляем временный PDF
        os.unlink(tmp_path)
        
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
            "• 🔗 Ссылку на чек ФНС\n\n"
            "Или используй команду /full_analyze для массовой обработки"
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
    application.add_handler(CommandHandler("full_analyze", full_analyze))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()