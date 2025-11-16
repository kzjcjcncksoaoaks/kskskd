import sqlite3
import os
from decimal import Decimal
from pathlib import Path

from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from assets.antispam import antispam, admin_only, antispam_earning
from assets.transform import transform_int as tr
from bot import bot
from commands.help import CONFIG
import config as cfg

from commands.db import cursor as cursorgdb
from user import BFGuser

# Создаем базовую реализацию kb модуля
class KBModule:
    @staticmethod
    def top(user_id, tab):
        """Базовая реализация top клавиатуры"""
        keyboards = InlineKeyboardMarkup(row_width=2)
        buttons = [
            InlineKeyboardButton("👑 Топ рейтинга", callback_data=f"top-rating|{user_id}|{tab}"),
            InlineKeyboardButton("💰 Топ денег", callback_data=f"top-balance|{user_id}|{tab}"),
            InlineKeyboardButton("🧰 Топ ферм", callback_data=f"top-cards|{user_id}|{tab}"),
            InlineKeyboardButton("🗄 Топ бизнесов", callback_data=f"top-bsterritory|{user_id}|{tab}"),
            InlineKeyboardButton("🏆 Топ опыта", callback_data=f"top-exp|{user_id}|{tab}"),
            InlineKeyboardButton("💴 Топ йен", callback_data=f"top-yen|{user_id}|{tab}"),
            InlineKeyboardButton("📦 Топ обычных кейсов", callback_data=f"top-case1|{user_id}|{tab}"),
            InlineKeyboardButton("🏵 Топ золотых кейсов", callback_data=f"top-case2|{user_id}|{tab}"),
            InlineKeyboardButton("🏺 Топ рудных кейсов", callback_data=f"top-case3|{user_id}|{tab}"),
            InlineKeyboardButton("🌌 Топ материальных кейсов", callback_data=f"top-case4|{user_id}|{tab}"),
            InlineKeyboardButton("👥 Топ рефералов", callback_data=f"ref-top|{user_id}|{tab}"),
        ]
        keyboards.add(*buttons)
        return keyboards

# Создаем экземпляр модуля клавиатур
assets_kb = KBModule()
original_kb = assets_kb.top


class SetRefSummState(StatesGroup):
    column = State()
    summ = State()


CONFIG['help_osn'] += '\n   👥 Реф'

CONFIG_VALUES = {
    'balance': ['user.balance', '$', ['', '', ''], '💰 Деньги'],
    'energy': ['user.energy', '⚡️', ['энергия', 'энергии', 'энергий'], '⚡️ Энергия'],
    'yen': ['user.yen', '💴', ['йена', 'йены', 'йен'], '💴 Йены'],
    'exp': ['user.exp', '💡', ['опыт', 'опыта', 'опытов'], '💡 Опыт'],
    'ecoins': ['user.bcoins', '💳', ['B-coin', 'B-coins', 'B-coins'], '💳 B-coins'],
    'corn': ['user.corn', '🥜', ['зерно', 'зерна', 'зёрен'], '🥜 Зерна'],
    'biores': ['user.biores', '☣️', ['биоресурс', 'биоресурса', 'биоресурсов'], '☣️ Биоресурсы'],
    'matter': ['user.mine.matter', '🌌', ['материя', 'материи', 'материй'], '🌌 Материя'],
}

# Создаем роутер
ref_router = Router()


def get_form(number: int, forms: list[str]) -> str:
    number = abs(int(number)) % 100
    if 11 <= number <= 19:
        return forms[2]
    last_digit = number % 10
    if last_digit == 1:
        return forms[0]
    if 2 <= last_digit <= 4:
        return forms[1]
    return forms[2]


def freward(key: str, amount: int) -> str:
    config = CONFIG_VALUES[key]
    symbol, forms = config[1], config[2]
    word_form = get_form(amount, forms)
    return f"{tr(amount)}{symbol} {word_form}"


def settings_kb(top) -> InlineKeyboardMarkup:
    keyboards = InlineKeyboardMarkup(row_width=1)
    txt = '➕ Добавить топ рефералов' if top == 0 else '❌ Удалить топ рефералов'
    keyboards.add(InlineKeyboardButton("✍️ Изменить награду", callback_data='ref-edit-prize'))
    keyboards.add(InlineKeyboardButton(txt, callback_data='ref-edit-top'))
    return keyboards


def select_values() -> InlineKeyboardMarkup:
    keyboards = InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    for key, value in CONFIG_VALUES.items():
        buttons.append(InlineKeyboardButton(value[3], callback_data=f'ref-set-prize_{key}'))
    
    keyboards.add(*buttons)
    keyboards.add(InlineKeyboardButton("❌ Закрыть", callback_data='ref-dell'))
    return keyboards


def top_substitution_kb(user_id, tab) -> InlineKeyboardMarkup:
    keyboards = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("👑 Топ рейтинга", callback_data=f"top-rating|{user_id}|{tab}"),
        InlineKeyboardButton("💰 Топ денег", callback_data=f"top-balance|{user_id}|{tab}"),
        InlineKeyboardButton("🧰 Топ ферм", callback_data=f"top-cards|{user_id}|{tab}"),
        InlineKeyboardButton("🗄 Топ бизнесов", callback_data=f"top-bsterritory|{user_id}|{tab}"),
        InlineKeyboardButton("🏆 Топ опыта", callback_data=f"top-exp|{user_id}|{tab}"),
        InlineKeyboardButton("💴 Топ йен", callback_data=f"top-yen|{user_id}|{tab}"),
        InlineKeyboardButton("📦 Топ обычных кейсов", callback_data=f"top-case1|{user_id}|{tab}"),
        InlineKeyboardButton("🏵 Топ золотых кейсов", callback_data=f"top-case2|{user_id}|{tab}"),
        InlineKeyboardButton("🏺 Топ рудных кейсов", callback_data=f"top-case3|{user_id}|{tab}"),
        InlineKeyboardButton("🌌 Топ материальных кейсов", callback_data=f"top-case4|{user_id}|{tab}"),
        InlineKeyboardButton("👥 Топ рефералов", callback_data=f"ref-top|{user_id}|{tab}"),
    ]
    
    keyboards.add(*buttons)
    return keyboards


def upd_keyboards(rtop: int) -> None:
    if rtop == 0:
        assets_kb.top = original_kb
    else:
        assets_kb.top = top_substitution_kb


class Database:
    def __init__(self):
        # Создаем директорию если не существует
        db_path = 'modules/temp/referrals.db'
        db_dir = os.path.dirname(db_path)
        
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"Создана директория: {db_dir}")
        
        # Альтернативный путь если основной не работает
        try:
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
            self.create_tables()
        except Exception as e:
            print(f"Ошибка при подключении к {db_path}: {e}")
            # Пробуем создать в текущей директории
            try:
                self.conn = sqlite3.connect('referrals.db')
                self.cursor = self.conn.cursor()
                self.create_tables()
                print("База данных создана в текущей директории: referrals.db")
            except Exception as e2:
                print(f"Критическая ошибка: {e2}")
                raise
    
    def create_tables(self) -> None:
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                ref INTEGER DEFAULT 0,
                balance TEXT DEFAULT '0'
            )''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                summ TEXT,
                column TEXT,
                rtop INTEGER DEFAULT 1
            )''')
        
        # Проверяем есть ли настройки
        rtop = self.cursor.execute('SELECT rtop FROM settings WHERE id = 1').fetchone()
        if not rtop:
            summ = 1_000_000_000_000_000
            self.cursor.execute('INSERT INTO settings (id, summ, column) VALUES (1, ?, ?)', (summ, 'balance'))
            rtop = 1
        else:
            rtop = rtop[0]
        self.conn.commit()
        
        upd_keyboards(rtop)
        print("Таблицы реферальной системы инициализированы")
        
    async def upd_settings(self, summ, column):
        self.cursor.execute('UPDATE settings SET summ = ?, column = ? WHERE id = 1', (summ, column))
        self.cursor.execute('UPDATE users SET balance = 0')
        self.conn.commit()
        
    async def upd_rtop(self, rtop):
        self.cursor.execute('UPDATE settings SET rtop = ? WHERE id = 1', (rtop,))
        self.conn.commit()
        
    async def get_rtop(self) -> int:
        result = self.cursor.execute('SELECT rtop FROM settings WHERE id = 1').fetchone()
        return result[0] if result else 1
    
    async def reg_user(self, user_id) -> None:
        try:
            ex = self.cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,)).fetchone()
            if not ex:
                self.cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
                self.conn.commit()
        except Exception as e:
            print(f"Ошибка при регистрации пользователя {user_id}: {e}")
    
    async def get_info(self, user_id) -> tuple:
        await self.reg_user(user_id)
        result = self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not result:
            return (user_id, 0, '0')
        return result
    
    async def get_summ(self) -> tuple:
        result = self.cursor.execute('SELECT summ, column FROM settings WHERE id = 1').fetchone()
        if not result:
            return ('1000000000000000', 'balance')
        return result
    
    async def upd_summ(self, summ) -> None:
        summ = "{:.0f}".format(summ)
        self.cursor.execute('UPDATE settings SET summ = ? WHERE id = 1', (summ,))
        self.conn.commit()
        
    async def new_ref(self, user_id, summ) -> None:
        await self.reg_user(user_id)
        try:
            rbalance = self.cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
            if not rbalance:
                rbalance = '0'
            else:
                rbalance = rbalance[0]
            
            new_rbalance = Decimal(str(rbalance)) + Decimal(str(summ))
            new_rbalance = "{:.0f}".format(new_rbalance)
            
            self.cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_rbalance, user_id))
            self.cursor.execute('UPDATE users SET ref = ref + 1 WHERE user_id = ?', (user_id,))
            self.conn.commit()
        except Exception as e:
            print(f"Ошибка при добавлении реферала: {e}")
        
    async def get_top(self) -> list:
        try:
            data = self.cursor.execute('SELECT user_id, ref FROM users ORDER BY ref DESC LIMIT 10').fetchall()
            users = []
            
            for user_id, ref in data:
                name = cursorgdb.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
                if name:
                    users.append((user_id, ref, name[0]))
            return users
        except Exception as e:
            print(f"Ошибка при получении топа: {e}")
            return []
        

# Создаем экземпляр базы данных
try:
    db = Database()
except Exception as e:
    print(f"Критическая ошибка при инициализации БД: {e}")
    # Создаем заглушку чтобы бот не падал
    db = None


@ref_router.message(F.text.lower().in_(['реф', '/ref']))
@antispam
async def ref(message: Message, user: BFGuser):
    if not db:
        await message.answer("❌ Реферальная система временно недоступна")
        return
        
    summ, column = await db.get_summ()
    data = await db.get_info(user.id)
    await message.answer(f'''https://t.me/{cfg.bot_username}?start=r{user.game_id}
<code>·······························</code>
{user.url}, твоя реферальная ссылка, можешь поделиться и получить {freward(column, summ)}

👥 <i>Твои рефералы</i>
<b>• {data[1]} чел.</b>
✨ <i>Заработано с рефералов:</i>
<b>• {freward(column, data[2])}</b>''')


async def on_start_event(event, *args):
    if not db:
        return
        
    try:
        message = args[0]['message']
        user_id = message.from_user.id
        r_id = int(message.text.split('/start r')[1])
        summ, column = await db.get_summ()
        
        user = cursorgdb.execute('SELECT game_id FROM users WHERE user_id = ?', (user_id,)).fetchone()
        real_id = cursorgdb.execute('SELECT user_id FROM users WHERE game_id = ?', (r_id,)).fetchone()
        
        if user_id == r_id or not real_id or user:
            return
        
        user = BFGuser(not_class=real_id[0])
        await user.update()
        
        # Упрощенная версия без eval для безопасности
        await update_user_balance(real_id[0], column, summ)
        await db.new_ref(real_id[0], summ)
        
        await bot.send_message(real_id[0], f'🥰 <b>Спасибо за приглашение!</b>\nНа ваш баланс зачислено {freward(column, summ)}')
    except Exception as e:
        print('ref error: ', e)


async def update_user_balance(user_id, column, summ):
    """Безопасное обновление баланса пользователя"""
    column_map = {
        'balance': 'balance',
        'energy': 'energy', 
        'yen': 'yen',
        'exp': 'exp',
        'ecoins': 'bcoins',
        'corn': 'corn',
        'biores': 'biores',
        'matter': 'matter'
    }
    
    if column in column_map:
        db_column = column_map[column]
        try:
            cursorgdb.execute(f"UPDATE users SET {db_column} = {db_column} + ? WHERE user_id = ?", (summ, user_id))
            cursorgdb.connection.commit()
        except Exception as e:
            print(f"Ошибка при обновлении баланса: {e}")


@ref_router.message(Command('refsetting'))
@antispam
@admin_only(private=True)
async def settings_cmd(message: Message, user: BFGuser):
    if not db:
        await message.answer("❌ Реферальная система временно недоступна")
        return
        
    summ, column = await db.get_summ()
    top = await db.get_rtop()
    await message.answer(f'{user.url}, текущая награда за реферала - {freward(column, summ)}', reply_markup=settings_kb(top))


@ref_router.callback_query(F.data == 'ref-dell')
async def dell_message_kb(call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception as e:
        print(e)


@ref_router.callback_query(F.data == 'ref-edit-prize')
async def select_prize_kb(call: CallbackQuery):
    if not db:
        await call.answer("❌ Реферальная система временно недоступна", show_alert=True)
        return
        
    await call.message.edit_text('👥 <b>Выберите валюту для награды:</b>', reply_markup=select_values())


@ref_router.callback_query(F.data.startswith('ref-set-prize_'))
async def edit_prize_kb(call: CallbackQuery, state: FSMContext):
    if not db:
        await call.answer("❌ Реферальная система временно недоступна", show_alert=True)
        return
        
    prize = call.data.split('_')[1]
    await call.message.edit_text(f'👥 Введите сумму награды ({CONFIG_VALUES[prize][3]}):\n\n<i>Для отмены введите "-"</i>')
    await state.update_data(column=prize)
    await state.set_state(SetRefSummState.summ)


@ref_router.message(SetRefSummState.summ)
async def enter_summ_cmd(message: Message, state: FSMContext):
    if not db:
        await message.answer("❌ Реферальная система временно недоступна")
        await state.clear()
        return
        
    if message.text == '-':
        await state.clear()
        await message.answer('Отменено.')
        return
    
    try:
        summ = int(message.text)
    except:
        await message.answer('Введите целое число.')
        return
    
    if summ <= 0:
        await message.answer('Ты серьёзно?')
        return
    
    data = await state.get_data()
    await db.upd_settings(summ, data['column'])
    
    await state.clear()
    await message.answer(f'✅ Установлена новая награда за реферала: {freward(data["column"], summ)}')


@ref_router.callback_query(F.data == 'ref-edit-top')
async def edit_top_kb(call: CallbackQuery):
    if not db:
        await call.answer("❌ Реферальная система временно недоступна", show_alert=True)
        return
        
    top = await db.get_rtop()
    new_top = 1 if top == 0 else 0
    upd_keyboards(new_top)
    await db.upd_rtop(new_top)
    await call.message.edit_reply_markup(settings_kb(new_top))


@ref_router.callback_query(F.data.startswith('ref-top'))
@antispam_earning
async def ref_top_kb(call: CallbackQuery, user: BFGuser):
    if not db:
        await call.answer("❌ Реферальная система временно недоступна", show_alert=True)
        return
        
    top = await db.get_top()
    tab = call.data.split('|')[2]
    
    if tab == 'ref':
        return
    
    top_message = f"{user.url}, топ 10 игроков бота по рефералам:\n"
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    if not top:
        top_message += "\n😕 Пока нет рефералов"
    else:
        for i, player in enumerate(top[:10], start=1):
            emj = emojis[i - 1] if i <= 10 else f"{i}."
            top_message += f"{emj} {player[2]} — {player[1]}👥\n"
    
    await call.message.edit_text(text=top_message, reply_markup=assets_kb.top(user.id, 'ref'), disable_web_page_preview=True)


def register_handlers(dp):
    dp.include_router(ref_router)
    # Если CastomEvent существует, подписываемся на событие
    try:
        from assets.classes import CastomEvent
        CastomEvent.subscribe('start_event', on_start_event)
        print("Реферальная система: подписка на start_event выполнена")
    except ImportError:
        print("CastomEvent не найден, пропускаем подписку на события")


MODULE_DESCRIPTION = {
    'name': '👥 Реферальная система',
    'description': 'Реферальная система\nЕсть возможность настроить награду за реферала\nКоманда /refsetting'
        }
