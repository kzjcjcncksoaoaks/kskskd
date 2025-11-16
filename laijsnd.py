import asyncio
from datetime import datetime
import sqlite3
import os
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from assets.transform import transform_int as tr
from assets.antispam import antispam, antispam_earning, new_earning, admin_only
from user import BFGuser


class SetSummState(StatesGroup):
    summ = State()


DEFOULT_PRIZES = {
    1: ['balance', 1_000_000_000_000, '💰 Денег'],
    2: ['btc', 1_000_000_000, '🌐 Биткоинов'],
    3: ['energy', 30, '⚡️ Энергии'],
    4: ['balance', 5_000_000_000_000, '💰 Денег'],
    5: ['yen', 100_000_000, '💴 Йен'],
    6: ['matter', 300, '🌌 Материи'],
    7: ['palladium', 1, '⚗️ Палладиум'],
    8: ['balance', 5_000_000_000_000, '💰 Денег'],
    9: ['matter', 500, '🌌 Материи'],
    10: ['energy', 30, '⚡️ Энергии'],
    11: ['exp', 3000, '💡 Опыта'],
    12: ['balance', 100_000_000_000_000, '💰 Денег'],
    13: ['balance', 500_000_000_000_000, '💰 Денег'],
    14: ['ecoins', 20, '💳 B-coins'],
}

PRIZES_CONFIG = {
    'balance': '💰 Денег',
    'btc': '🌐 Биткоинов',
    'energy': '⚡️ Энергии',
    'yen': '💴 Йен',
    'exp': '💡 Опыта',
    'ecoins': '💳 B-coins',
    'case1': '📦 Обычный кейс',
    'case2': '🏵 Золотой кейс',
    'case3': '🏺 Рудный кейс',
    'case4': '🌌 Материальный кейс',
    'rating': '👑 Рейтинга',
    'corn': '🥜 Зёрна',
    'biores': '☣️ Биоресурсов',
    'titanium': '⚙️ Титана',
    'palladium': '⚗️ Палладий',
    'matter': '🌌 Материи',
}


class Database:
    def __init__(self):
        # Создаем директорию если её нет
        db_dir = Path('modules/temp')
        db_dir.mkdir(parents=True, exist_ok=True)
        
        db_path = db_dir / 'winter_calendar.db'
        self.conn = sqlite3.connect(str(db_path))
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self) -> None:
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                day INTEGER DEFAULT '0'
            )''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS info (
                day INTEGER
            )''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS prize (
                day INTEGER,
                column TEXT,
                summ INTEGER,
                info TEXT
            )''')
        self.conn.commit()
        
        if not self.cursor.execute('SELECT * FROM info').fetchone():
            self.cursor.execute('INSERT INTO info (day) VALUES (?)', (1,))
            self.conn.commit()
            
        self.creat_prizes_list()
        
    def creat_prizes_list(self) -> None:
        if not self.cursor.execute('SELECT * FROM prize').fetchone():
            for day, i in DEFOULT_PRIZES.items():
                self.cursor.execute('INSERT INTO prize (day, column, summ, info) VALUES (?, ?, ?, ?)', (day, i[0], i[1], i[2]))
            self.conn.commit()
            
    async def upd_prize(self, day, column, summ) -> None:
        info = PRIZES_CONFIG[column]
        self.cursor.execute('UPDATE prize SET column = ?, summ = ?, info = ? WHERE day = ?', (column, summ, info, day))
        self.conn.commit()
            
    async def get_prizes(self) -> dict:
        data = self.cursor.execute('SELECT * FROM prize').fetchall()
        return {item[0]: list(item[1:]) for item in data}

    async def get_day(self) -> int:
        return self.cursor.execute('SELECT day FROM info').fetchone()[0]

    async def get_user_day(self, user_id) -> int:
        day = self.cursor.execute('SELECT day FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not day:
            self.cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            self.conn.commit()
            return 0
        return day[0]
    
    async def prize_received(self, user_id) -> None:
        day = self.cursor.execute('SELECT day FROM info').fetchone()[0]
        self.cursor.execute('UPDATE users SET day = ? WHERE user_id = ?', (day, user_id))
        self.conn.commit()
    
    async def upd_day(self) -> None:
        self.cursor.execute('UPDATE info SET day = day + 1')
        self.conn.commit()


# Инициализация базы данных
db = Database()


def get_prize_kb() -> InlineKeyboardMarkup:
    keyboards = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить", callback_data="winter-event-get-prize")]
    ])
    return keyboards


def info_prizes_kb(data, lday, user_id) -> InlineKeyboardMarkup:
    buttons = []
    for day, i in data.items():
        txt = '📍 |' if day == lday else ''
        buttons.append([InlineKeyboardButton(
            text=f"{txt} {tr(i[1])} {i[2]}", 
            callback_data=f"winter-edit-prize_{day}|{user_id}"
        )])
    
    keyboards = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboards


def edit_prizes_kb(day) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    
    for i, (key, item) in enumerate(PRIZES_CONFIG.items()):
        row.append(InlineKeyboardButton(text=item, callback_data=f"winter-set-prize_{day}_{key}"))
        if (i + 1) % 3 == 0:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="winter-dell")])
    
    keyboards = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboards


@antispam
async def event_calendar_cmd(message: Message, user: BFGuser):
    try:
        day = await db.get_day()
        prize = await db.get_prizes()
        prize = prize.get(day)
        
        if not prize:
            await message.answer(f'<b>{user.url}, месяц подарков к концу! Возвращайтесь в следующем году 🎅</b>')
            return
        
        msg = await message.answer(
            f'<b>{user.url}, сегодняшний подарок </b>(<code>{day}</code>/<code>14</code>)</b>: {tr(prize[1])} {prize[2]}', 
            reply_markup=get_prize_kb()
        )
        await new_earning(msg)
    except Exception as e:
        await message.answer(f'❌ Ошибка при получении календаря: {str(e)}')


@antispam_earning
async def event_calendar_call(call: CallbackQuery, user: BFGuser):
    try:
        day = await db.get_day()
        user_day = await db.get_user_day(user.user_id)
        prize = await db.get_prizes()
        prize = prize.get(day)

        if user_day >= day or not prize:
            await call.answer(f'<b>{user.name}, Вы уже забрали свой подарок сегодня! 🎅</b>')
            return

        upd_list = {
            'balance': user.balance,
            'btc': user.btc,
            'energy': user.energy,
            'yen': user.yen,
            'exp': user.expe,
            'ecoins': user.bcoins,
            'case1': user.case[1],
            'case2': user.case[2],
            'case3': user.case[3],
            'case4': user.case[4],
            'rating': user.rating,
            'corn': user.corn,
            'biores': user.biores,
            'titanium': user.mine.titanium,
            'palladium': user.mine.palladium,
            'matter': user.mine.matter,
        }

        await upd_list[prize[0]].upd(prize[1], '+')
        await call.answer(text=f'{user.name}, Вы получили: {tr(prize[1])} {prize[2]} 🎅', show_alert=True)
        await db.prize_received(user.user_id)
    except Exception as e:
        await call.answer(f'❌ Ошибка при получении подарка: {str(e)}', show_alert=True)


@antispam
@admin_only(private=True)
async def edit_prizes_cmd(message: Message, user: BFGuser):
    try:
        day = await db.get_day()
        prize = await db.get_prizes()
        
        await message.answer(
            '🎅 <b>ХО-ХО-ХО! Новогодняя доставка! Получите и распишитесь:</b>', 
            reply_markup=info_prizes_kb(prize, day, user.user_id)
        )
    except Exception as e:
        await message.answer(f'❌ Ошибка при редактировании календаря: {str(e)}')


async def edit_prize_kb(call: CallbackQuery):
    try:
        day = int(call.data.split('_')[1].split('|')[0])
        await call.message.edit_text(
            f'🎅 Выберите новую награду для дня <b>#{day}</b>:', 
            reply_markup=edit_prizes_kb(day)
        )
    except Exception as e:
        await call.answer(f'❌ Ошибка: {str(e)}', show_alert=True)


async def edit_summ_kb(call: CallbackQuery, state: FSMContext):
    try:
        day = int(call.data.split('_')[1])
        prize = call.data.split('_')[2].split('|')[0]
        await call.message.edit_text(
            f'🎅 Введите сумму для дня <b>#{day} ({PRIZES_CONFIG[prize]})</b>:\n\n<i>Для отмены введите "-"</i>'
        )
        await state.update_data(column=prize, day=day)
        await state.set_state(SetSummState.summ)
    except Exception as e:
        await call.answer(f'❌ Ошибка: {str(e)}', show_alert=True)


async def dell_message_kb(call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception as e:
        print(e)


async def set_summ_cmd(message: Message, state: FSMContext):
    try:
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
        await db.upd_prize(data['day'], data['column'], summ)
        
        txt = PRIZES_CONFIG[data['column']]
        await message.answer(f'🎅 Установленна новая награда на <b>#{data["day"]}</b> день: <code>{tr(summ)} {txt}</code>')
        await state.clear()
    except Exception as e:
        await message.answer(f'❌ Ошибка при установке суммы: {str(e)}')


async def check() -> None:
    while True:
        try:
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                await db.upd_day()
                await asyncio.sleep(120)
            await asyncio.sleep(15)
        except Exception as e:
            print(f"Ошибка в фоновой задаче: {e}")
            await asyncio.sleep(60)


# Создание роутера
router = Router()

@router.message(F.text.lower() == 'календарь')
async def calendar_handler(message: Message, user: BFGuser):
    await event_calendar_cmd(message, user)

@router.callback_query(F.data == "winter-event-get-prize")
async def get_prize_handler(call: CallbackQuery, user: BFGuser):
    await event_calendar_call(call, user)

@router.message(Command("wcalendar"))
async def wcalendar_handler(message: Message, user: BFGuser):
    await edit_prizes_cmd(message, user)

@router.callback_query(F.data.startswith("winter-edit-prize_"))
async def edit_prize_handler(call: CallbackQuery):
    await edit_prize_kb(call)

@router.callback_query(F.data.startswith("winter-set-prize_"))
async def set_prize_handler(call: CallbackQuery, state: FSMContext):
    await edit_summ_kb(call, state)

@router.callback_query(F.data == "winter-dell")
async def dell_handler(call: CallbackQuery):
    await dell_message_kb(call)

@router.message(SetSummState.summ)
async def summ_state_handler(message: Message, state: FSMContext):
    await set_summ_cmd(message, state)


# Глобальная переменная для отслеживания регистрации
_router_registered = False

def register_handlers(dp):
    global _router_registered
    if not _router_registered:
        dp.include_router(router)
        _router_registered = True


MODULE_DESCRIPTION = {
    'name': '☃️ Winter calendar',
    'description': '''Ивент-модуль зима:
- Новое оформление
- Ивент календарь (команда "календарь")

* Модуль использует собственную базу данных"
* Для настройки наград введите /wcalendar (лс)'''
}

# Запуск фоновой задачи
try:
    loop = asyncio.get_event_loop()
    loop.create_task(check())
except:
    # Если loop уже запущен
    asyncio.create_task(check())
