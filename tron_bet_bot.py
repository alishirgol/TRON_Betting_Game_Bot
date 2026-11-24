import json
import aiofiles
import asyncio
import random
import uuid
from datetime import datetime, date
from pathlib import Path
import os
from typing import Dict, List, Any, Optional, Tuple
from rubka.asynco import Robot, filters, Message
from rubka.keypad import ChatKeypadBuilder, InlineBuilder

# ============================================================
#  تنظیمات ربات (فقط این بخش را برای دوستان ویرایش کنید)
# ============================================================

# توکن ربات روبیکا (از بات‌فادر روبیکا گرفته می‌شود).
# ⚠️ هر کسی این توکن را داشته باشد کنترل کامل ربات را دارد؛ برای دوستان توکن ربات خودشان را بگذارید.
# اگر مقدار را «TOKEN_HERE» بگذارید، ربات هنگام اجرا پیام «توکن را قرار دهید» می‌دهد و بالا نمی‌آید.
TOKEN = "FADKS"

# لیست GUID مدیران اصلی ربات.
# این افراد به دستورهای مدیریتی (شارژ/کسر ترون، ادمین کردن و عزل کاربران، تغییر وضعیت کاربر) دسترسی دارند.
# ⚠️ برای دوستان حتماً با GUID خودشان جایگزین کنید.
ADMIN_IDS = ["u0Ihfd1dec"]

# GUID کانال اصلی برای بررسی عضویت اجباری (دکمه‌ی «عضو شدم»؛ کاربر باید در هر دو کانال عضو باشد).
GUID_CHANNEL = "c0Cvb1a6"

# GUID کانال دوم (کانال اسپانسر) برای بررسی عضویت اجباری.
GUID_CHANNEL_SPONSOR = "c0BiLc0b7"

# آیدی کانال اصلی — در پیام‌های ربات (خوش‌آمد، منوها، عضویت اجباری) برای تبلیغ کانال نمایش داده می‌شود.
CHANNEL_MAIN = "@"

# آیدی کانال دوم — کنار کانال اصلی در پیام‌های عضویت اجباری نمایش داده می‌شود.
CHANNEL_SECOND = "@Liih"

class ChatDatabase:
    def __init__(self, file_path="chats.json"):
        self.file_path = Path(file_path)
        self._load()
    def _load(self):
        if not self.file_path.exists():
            data = {"chats": []}
            self.file_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
        self.db = json.loads(self.file_path.read_text(encoding="utf-8"))
    def _save(self):
        self.file_path.write_text(json.dumps(self.db, indent=4), encoding="utf-8")
    def add_chat(self, chat_id: str):
        if chat_id not in self.db["chats"]:
            self.db["chats"].append(chat_id)
            self._save()
            return True
        return False
    def has_chat(self, chat_id: str) -> bool:
        return chat_id in self.db["chats"]
class Config:
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    USERS_DB = DATA_DIR / "users.json"
    GROUPS_DB = DATA_DIR / "groups.json"
    BETS_DB = DATA_DIR / "bets.json"
    DAILY_STATS_DB = DATA_DIR / "daily_stats.json"
    BOT_TOKEN = TOKEN
    MIN_BET = 10
    MAX_BET = 1000000
    MIN_MULTIPLIER = 1.0
    MAX_MULTIPLIER = 20.0
    START_BONUS = 200
    MAX_DAILY_BETS = 20
    MAX_BETS_INCREASE_COST = 20000
    MAX_BETS_INCREASE_AMOUNT = 10
    DAILY_WITHDRAW_LIMIT = 10000
    WITHDRAW_TAX = 0.10
    TITLES = {
        "تازه‌وارد": 0,
        "سرباز": 100,
        "شوالیه": 300,
        "بارون": 600,
        "کنت": 1000,
        "دوک": 1500,
        "شاهزاده": 2500,
        "پادشاه": 5000,
        "قیصر": 10000,
        "خداوندگار": 25000,
        "سلطان": 50000,
        "اسطوره": 100000,
        "صدراعظم": 150000
    }
    ADMINS = ADMIN_IDS
class JSONDatabase:
    def __init__(self):
        self.users = {}
        self.groups = {}
        self.bets = {}
        self.daily_stats = {}
        self.lock = asyncio.Lock()
    async def load_data(self, file_path, default_data):
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content else default_data
        except (FileNotFoundError, json.JSONDecodeError):
            return default_data
    async def save_data(self, file_path, data):
        async with self.lock:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
    async def initialize(self):
        self.users = await self.load_data(Config.USERS_DB, {})
        self.groups = await self.load_data(Config.GROUPS_DB, {})
        self.bets = await self.load_data(Config.BETS_DB, {})
        self.daily_stats = await self.load_data(Config.DAILY_STATS_DB, {})
        updated = False
        for user_id, user in self.users.items():
            if "max_bets_per_day" not in user:
                user["max_bets_per_day"] = Config.MAX_DAILY_BETS
                updated = True
            if "daily_bets_today" not in user:
                user["daily_bets_today"] = 0
                updated = True
            if "daily_withdrawn_today" not in user:
                user["daily_withdrawn_today"] = 0
                updated = True
            if "total_withdrawn" not in user:
                user["total_withdrawn"] = 0
                updated = True
            if "vip_level" not in user:
                user["vip_level"] = 0
                updated = True
            if "draws" not in user:
                user["draws"] = 0
                updated = True
            if "last_daily_reset" not in user:
                user["last_daily_reset"] = date.today().isoformat()
                updated = True
        if updated:
            await self.save_data(Config.USERS_DB, self.users)
        print("✅ دیتابیس‌های پیشرفته بارگذاری شدند")
    async def get_user(self, user_id: str) -> Dict:
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                "id": user_id,
                "tron": Config.START_BONUS,
                "title": "تازه‌وارد",
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "total_bet": 0,
                "total_won": 0,
                "max_bets_per_day": Config.MAX_DAILY_BETS,
                "daily_bets_today": 0,
                "daily_withdrawn_today": 0,
                "total_withdrawn": 0,
                "role": "user",
                "vip_level": 0,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "last_daily_reset": date.today().isoformat()
            }
            await self.save_data(Config.USERS_DB, self.users)
        return self.users[user_id]
    async def update_user(self, user_id: str, updates: Dict):
        user_id = str(user_id)
        user = await self.get_user(user_id)
        user.update(updates)
        user["last_active"] = datetime.now().isoformat()
        self.users[user_id] = user
        await self.save_data(Config.USERS_DB, self.users)
    async def reset_daily_stats(self, user_id: str):
        today = date.today().isoformat()
        user = await self.get_user(user_id)
        if user.get("last_daily_reset") != today:
            await self.update_user(user_id, {
                "daily_bets_today": 0,
                "daily_withdrawn_today": 0,
                "last_daily_reset": today
            })
    async def can_user_bet(self, user_id: str) -> Tuple[bool, str]:
        await self.reset_daily_stats(user_id)
        user = await self.get_user(user_id)
        max_bets = user.get("max_bets_per_day", Config.MAX_DAILY_BETS)
        daily_bets = user.get("daily_bets_today", 0)
        if daily_bets >= max_bets:
            return False, f"❌ امروز بیش از حد شرط بسته‌اید!\n📊 باقیمانده شرط‌های امروز: 0"
        return True, "✅ می‌توانید شرط ببندید"
    async def increment_daily_bet(self, user_id: str):
        user = await self.get_user(user_id)
        new_count = user.get("daily_bets_today", 0) + 1
        await self.update_user(user_id, {"daily_bets_today": new_count})
    async def increase_max_bets(self, user_id: str) -> Tuple[bool, str]:
        user = await self.get_user(user_id)
        success, new_balance = await self.deduct_tron(user_id, Config.MAX_BETS_INCREASE_COST)
        if not success:
            return False, "❌ موجودی کافی نیست!"
        current_max = user.get("max_bets_per_day", Config.MAX_DAILY_BETS)
        new_max = current_max + Config.MAX_BETS_INCREASE_AMOUNT
        await self.update_user(user_id, {
            "max_bets_per_day": new_max,
            "vip_level": user.get("vip_level", 0) + 1
        })
        return True, f"✅ محدودیت شرط روزانه افزایش یافت!\n🎯 جدید: {new_max} شرط در روز"
    async def withdraw_tron(self, user_id: str, amount: float) -> Tuple[bool, str, float]:
        await self.reset_daily_stats(user_id)
        user = await self.get_user(user_id)
        daily_limit = Config.DAILY_WITHDRAW_LIMIT
        daily_withdrawn = user.get("daily_withdrawn_today", 0)
        if daily_withdrawn + amount > daily_limit:
            remaining = daily_limit - daily_withdrawn
            return False, f"❌ بیش از حد مجاز روزانه!\n💰 باقیمانده امروز: {remaining} ترون", 0
        tax = amount * Config.WITHDRAW_TAX
        total_deduction = amount + tax
        success, new_balance = await self.deduct_tron(user_id, total_deduction)
        if not success:
            return False, f"❌ موجودی کافی نیست!\n💰 نیاز: {total_deduction:.2f} ترون", 0
        new_daily_withdrawn = daily_withdrawn + amount
        new_total_withdrawn = user.get("total_withdrawn", 0) + amount
        await self.update_user(user_id, {
            "daily_withdrawn_today": new_daily_withdrawn,
            "total_withdrawn": new_total_withdrawn
        })
        return True, f"✅ برداشت موفق!\n💸 مبلغ: {amount} ترون\n💰 مالیات: {tax:.2f} ترون", amount
    async def add_tron(self, user_id: str, amount: float):
        user = await self.get_user(user_id)
        new_balance = user.get("tron", 0) + amount
        await self.update_user(user_id, {"tron": new_balance})
        return new_balance
    async def deduct_tron(self, user_id: str, amount: float) -> Tuple[bool, float]:
        user = await self.get_user(user_id)
        current_balance = user.get("tron", 0)
        if current_balance >= amount:
            new_balance = current_balance - amount
            await self.update_user(user_id, {"tron": new_balance})
            return True, new_balance
        return False, current_balance
    async def get_top_users(self, limit: int = 10) -> List[Dict]:
        users_list = list(self.users.values())
        sorted_users = sorted(users_list, key=lambda x: x.get("tron", 0), reverse=True)
        return sorted_users[:limit]
    async def update_user_stats(self, user_id: str, won: bool, bet_amount: float, won_amount: float = 0, is_draw: bool = False):
        user = await self.get_user(user_id)
        updates = {
            "total_bet": user.get("total_bet", 0) + bet_amount
        }
        if is_draw:
            updates["draws"] = user.get("draws", 0) + 1
        elif won:
            updates["wins"] = user.get("wins", 0) + 1
            updates["total_won"] = user.get("total_won", 0) + won_amount
        else:
            updates["losses"] = user.get("losses", 0) + 1
        current_title = user.get("title", "تازه‌وارد")
        current_tron = user.get("tron", 0)
        new_title = current_title
        for title, price in sorted(Config.TITLES.items(), key=lambda x: x[1]):
            if current_tron >= price:
                new_title = title
        if new_title != current_title:
            updates["title"] = new_title
        await self.update_user(user_id, updates)
    async def add_bet(self, bet_id: str, bet_data: Dict):
        self.bets[bet_id] = {
            **bet_data,
            "id": bet_id,
            "created_at": datetime.now().isoformat()
        }
        await self.save_data(Config.BETS_DB, self.bets)
    async def is_admin(self, user_id: str) -> bool:
        user = await self.get_user(user_id)
        return user.get("role") in ["admin", "owner"] or user_id in Config.ADMINS
class GameEngine:
    @staticmethod
    def convert_to_english_numbers(text: str) -> str:
        persian_numbers = '۰۱۲۳۴۵۶۷۸۹'
        arabic_numbers = '٠١٢٣٤٥٦٧٨٩'
        english_numbers = '0123456789'
        for p, a, e in zip(persian_numbers, arabic_numbers, english_numbers):
            text = text.replace(p, e).replace(a, e)
        return text
    @staticmethod
    def parse_amount(text: str) -> Optional[float]:
        try:
            cleaned = ''.join(c for c in text if c.isdigit() or c in '.,')
            cleaned = GameEngine.convert_to_english_numbers(cleaned)
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except:
            return None
    @staticmethod
    async def play_number_guess(user_number: int, bet_amount: float, multiplier: float) -> Tuple[bool, float, Dict]:
        bot_number = random.randint(0, 10)
        if user_number == bot_number:
            win_amount = bet_amount * multiplier
            return True, win_amount, {
                "game": "number_guess",
                "user_number": user_number,
                "bot_number": bot_number,
                "multiplier": multiplier
            }
        else:
            return False, 0, {
                "game": "number_guess",
                "user_number": user_number,
                "bot_number": bot_number
            }
    @staticmethod
    async def play_rock_paper_scissors(user_choice: str, bet_amount: float, multiplier: float) -> Tuple[bool, float, Dict]:
        choices = ["سنگ", "کاغذ", "قیچی"]
        choice_map = {
            "سنگ": "سنگ", "sang": "سنگ", "rock": "سنگ", "1": "سنگ",
            "کاغذ": "کاغذ", "kaghaz": "کاغذ", "paper": "کاغذ", "2": "کاغذ",
            "قیچی": "قیچی", "gheychi": "قیچی", "scissors": "قیچی", "3": "قیچی"
        }
        user_choice = choice_map.get(user_choice.lower(), "سنگ")
        bot_choice = random.choice(choices)
        win_conditions = {
            "سنگ": "قیچی",
            "کاغذ": "سنگ",
            "قیچی": "کاغذ"
        }
        if user_choice == bot_choice:
            return False, bet_amount, {
                "game": "rock_paper_scissors",
                "user_choice": user_choice,
                "bot_choice": bot_choice,
                "result": "draw"
            }
        elif win_conditions[user_choice] == bot_choice:
            win_amount = bet_amount * multiplier
            return True, win_amount, {
                "game": "rock_paper_scissors",
                "user_choice": user_choice,
                "bot_choice": bot_choice,
                "multiplier": multiplier
            }
        else:
            return False, 0, {
                "game": "rock_paper_scissors",
                "user_choice": user_choice,
                "bot_choice": bot_choice
            }
    @staticmethod
    async def play_dice(bet_amount: float, multiplier: float) -> Tuple[bool, float, Dict]:
        user_dice = random.randint(1, 6)
        bot_dice = random.randint(1, 6)
        if user_dice > bot_dice:
            win_amount = bet_amount * multiplier
            return True, win_amount, {
                "game": "dice",
                "user_dice": user_dice,
                "bot_dice": bot_dice,
                "multiplier": multiplier
            }
        elif user_dice == bot_dice:
            return False, bet_amount, {
                "game": "dice",
                "user_dice": user_dice,
                "bot_dice": bot_dice,
                "result": "draw"
            }
        else:
            return False, 0, {
                "game": "dice",
                "user_dice": user_dice,
                "bot_dice": bot_dice
            }
    @staticmethod
    async def play_blackjack(bet_amount: float, multiplier: float) -> Tuple[bool, float, Dict]:
        suits = ["♥", "♦", "♣", "♠"]
        values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        def get_card_value(card: str) -> int:
            if card in ["J", "Q", "K"]:
                return 10
            elif card == "A":
                return 11
            else:
                return int(card)
        user_cards = []
        user_score = 0
        aces = 0
        for _ in range(2):
            value = random.choice(values)
            suit = random.choice(suits)
            user_cards.append(f"{value}{suit}")
            card_val = get_card_value(value)
            user_score += card_val
            if value == "A":
                aces += 1
        while user_score > 21 and aces > 0:
            user_score -= 10
            aces -= 1
        dealer_cards = []
        dealer_score = 0
        dealer_aces = 0
        for _ in range(2):
            value = random.choice(values)
            suit = random.choice(suits)
            dealer_cards.append(f"{value}{suit}")
            card_val = get_card_value(value)
            dealer_score += card_val
            if value == "A":
                dealer_aces += 1
        while dealer_score > 21 and dealer_aces > 0:
            dealer_score -= 10
            dealer_aces -= 1
        while dealer_score < 17:
            value = random.choice(values)
            suit = random.choice(suits)
            dealer_cards.append(f"{value}{suit}")
            card_val = get_card_value(value)
            dealer_score += card_val
            if value == "A":
                dealer_aces += 1
            while dealer_score > 21 and dealer_aces > 0:
                dealer_score -= 10
                dealer_aces -= 1
        if user_score > 21:
            result = "باخت"
            win_amount = 0
            won = False
        elif dealer_score > 21:
            result = "برد"
            win_amount = bet_amount * multiplier
            won = True
        elif user_score > dealer_score:
            result = "برد"
            win_amount = bet_amount * multiplier
            won = True
        elif user_score == dealer_score:
            result = "مساوی"
            win_amount = bet_amount
            won = False
        else:
            result = "باخت"
            win_amount = 0
            won = False
        return won, win_amount, {
            "game": "blackjack",
            "user_cards": user_cards,
            "user_score": user_score,
            "dealer_cards": dealer_cards,
            "dealer_score": dealer_score,
            "result": result,
            "multiplier": multiplier if won else None
        }
    @staticmethod
    async def play_poker(bet_amount: float, multiplier: float) -> Tuple[bool, float, Dict]:
        hands = [
            "بدون دست", "یک جفت", "دو جفت", "سه تایی", "استریت",
            "فلاش", "فول هاوس", "کاره", "استریت فلاش", "رویال فلاش"
        ]
        probabilities = [0.5, 0.3, 0.1, 0.05, 0.02, 0.01, 0.008, 0.005, 0.001, 0.0001]
        user_hand = random.choices(hands, weights=probabilities)[0]
        user_hand_index = hands.index(user_hand)
        bot_hand = random.choices(hands, weights=probabilities)[0]
        bot_hand_index = hands.index(bot_hand)
        if user_hand_index > bot_hand_index:
            win_amount = bet_amount * multiplier * (user_hand_index + 1) * 0.5
            won = True
        elif user_hand_index < bot_hand_index:
            win_amount = 0
            won = False
        else:
            win_amount = bet_amount * 0.5
            won = False
        return won, win_amount, {
            "game": "poker",
            "user_hand": user_hand,
            "bot_hand": bot_hand,
            "multiplier": multiplier if won else None,
            "hand_strength": user_hand_index
        }
    @staticmethod
    async def play_hokm(bet_amount: float, multiplier: float) -> Tuple[bool, float, Dict]:
        suits = ["♥", "♦", "♣", "♠"]
        values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        card_power = {value: idx for idx, value in enumerate(values)}
        hokm = random.choice(suits)
        user_cards = []
        user_power = 0
        for _ in range(4):
            value = random.choice(values)
            suit = random.choice(suits)
            user_cards.append(f"{value}{suit}")
            power = card_power[value]
            if suit == hokm:
                power += 13
            user_power += power
        bot_cards = []
        bot_power = 0
        for _ in range(4):
            value = random.choice(values)
            suit = random.choice(suits)
            bot_cards.append(f"{value}{suit}")
            power = card_power[value]
            if suit == hokm:
                power += 13
            bot_power += power
        if user_power > bot_power:
            win_amount = bet_amount * multiplier
            won = True
        elif user_power < bot_power:
            win_amount = 0
            won = False
        else:
            win_amount = bet_amount
            won = False
        return won, win_amount, {
            "game": "hokm",
            "user_cards": user_cards,
            "user_power": user_power,
            "bot_cards": bot_cards,
            "bot_power": bot_power,
            "hokm": hokm,
            "multiplier": multiplier if won else None
        }
    @staticmethod
    async def play_slot(bet_amount: float, multiplier: float) -> Tuple[bool, float, Dict]:
        symbols = ["🍒", "🍋", "🍊", "🍇", "🔔", "⭐", "7️⃣", "💎"]
        reels = []
        for _ in range(3):
            reel = [random.choice(symbols) for _ in range(3)]
            reels.append(reel)
        winning_lines = []
        if reels[0][1] == reels[1][1] == reels[2][1]:
            winning_lines.append("middle_horizontal")
        for i in range(3):
            if reels[0][i] == reels[1][i] == reels[2][i]:
                winning_lines.append(f"horizontal_{i+1}")
        if reels[0][0] == reels[1][1] == reels[2][2]:
            winning_lines.append("diagonal_down")
        if reels[0][2] == reels[1][1] == reels[2][0]:
            winning_lines.append("diagonal_up")
        if winning_lines:
            symbol_values = {
                "🍒": 2, "🍋": 3, "🍊": 4, "🍇": 5,
                "🔔": 8, "⭐": 10, "7️⃣": 20, "💎": 50
            }
            winning_symbol = reels[0][1] if reels[0][1] == reels[1][1] == reels[2][1] else reels[0][0]
            symbol_value = symbol_values.get(winning_symbol, 1)
            lines_count = len(winning_lines)
            win_amount = bet_amount * multiplier * symbol_value * lines_count * 0.1
            won = True
        else:
            win_amount = 0
            won = False
        slot_display = f"""
        ┌─────────┐
        │ {reels[0][0]} │ {reels[1][0]} │ {reels[2][0]} │
        ├─────────┤
        │ {reels[0][1]} │ {reels[1][1]} │ {reels[2][1]} │ ←
        ├─────────┤
        │ {reels[0][2]} │ {reels[1][2]} │ {reels[2][2]} │
        └─────────┘
        """
        return won, win_amount, {
            "game": "slot",
            "reels": reels,
            "winning_lines": winning_lines,
            "slot_display": slot_display,
            "multiplier": multiplier if won else None
        }
    @staticmethod
    def validate_bet(bet_amount: float, multiplier: float, user_balance: float) -> Tuple[bool, str]:
        if bet_amount < Config.MIN_BET:
            return False, f"حداقل شرط {Config.MIN_BET} ترون است! ❌"
        if bet_amount > Config.MAX_BET:
            return False, f"حداکثر شرط {Config.MAX_BET} ترون است! ❌"
        if bet_amount > user_balance:
            return False, f"موجودی کافی نیست! موجودی شما: {user_balance} ترون 💰"
        if multiplier < Config.MIN_MULTIPLIER or multiplier > Config.MAX_MULTIPLIER:
            return False, f"ضریب باید بین {Config.MIN_MULTIPLIER} تا {Config.MAX_MULTIPLIER} باشد! 📊"
        return True, "شرط معتبر است ✅"
class TronBot:
    def __init__(self):
        self.bot = Robot(
            token=Config.BOT_TOKEN,
            session_name="tron_bot_pro",
            safeSendMode=True,
            api_endpoint='messenger'
        )
        self.db = JSONDatabase()
        self.game_engine = GameEngine()
        self.user_states = {}
        self.chat_db = ChatDatabase("chats.json")
    def build_main_keypad(self):
        return (
            ChatKeypadBuilder()
            .row(
                ChatKeypadBuilder().button(id="start_bet", text="🎰 شروع شرط‌بندی"),
                ChatKeypadBuilder().button(id="profile", text="👤 پروفایل"),
            )
            .row(
                ChatKeypadBuilder().button(id="leaderboard", text="🏆 جدول امتیازات"),
                ChatKeypadBuilder().button(id="shop", text="🛒 فروشگاه لقب"),
            )
            .row(
                ChatKeypadBuilder().button(id="withdraw", text="💰 برداشت"),
                ChatKeypadBuilder().button(id="increase_limit", text="📈 افزایش محدودیت"),
            )
            .row(
                ChatKeypadBuilder().button(id="help", text="❓ راهنما"),
            )
            .build()
        )
    def build_bet_keypad(self):
        return (
            ChatKeypadBuilder()
            .row(
                ChatKeypadBuilder().button(id="number_game", text="🔢 اعداد"),
                ChatKeypadBuilder().button(id="rps_game", text="✂️ سنگ‌کاغذ‌قیچی"),
            )
            .row(
                ChatKeypadBuilder().button(id="dice_game", text="🎲 تاس"),
                ChatKeypadBuilder().button(id="blackjack_game", text="🃏 بلک‌جک"),
            )
            .row(
                ChatKeypadBuilder().button(id="poker_game", text="🎴 پوکر"),
                ChatKeypadBuilder().button(id="hokm_game", text="♠️ حکم"),
            )
            .row(
                ChatKeypadBuilder().button(id="slot_game", text="🎰 اسلات"),
                ChatKeypadBuilder().button(id="cancel_bet", text="❌ لغو"),
            )
            .row(
                ChatKeypadBuilder().button(id="back", text="🔙 بازگشت"),
            )
            .build()
        )
    def build_shop_keypad(self, user_tron: float):
        keypad = ChatKeypadBuilder()
        row_buttons = []
        for idx, (title, price) in enumerate(Config.TITLES.items()):
            if price > 0:
                can_buy = user_tron >= price
                emoji = "💰" if can_buy else "🔒"
                text = f"{emoji} {title}"
                row_buttons.append(
                    ChatKeypadBuilder().button(id=f"buy_{title}", text=text)
                )
                if len(row_buttons) == 2:
                    keypad.row(*row_buttons)
                    row_buttons = []
        if row_buttons:
            keypad.row(*row_buttons)
        keypad.row(ChatKeypadBuilder().button(id="back", text="🔙 بازگشت"))
        return keypad.build()
    async def get_user_state(self, user_id: str, group_id: str = None) -> Dict:
        key = f"{user_id}_{group_id}" if group_id else user_id
        if key not in self.user_states:
            self.user_states[key] = {}
        return self.user_states[key]
    async def set_user_state(self, user_id: str, state: Dict, group_id: str = None):
        key = f"{user_id}_{group_id}" if group_id else user_id
        self.user_states[key] = state
    async def clear_user_state(self, user_id: str, group_id: str = None):
        key = f"{user_id}_{group_id}" if group_id else user_id
        if key in self.user_states:
            del self.user_states[key]
    async def show_withdraw_menu(self, message: Message, user_id: str):
        user = await self.db.get_user(user_id)
        is_private = message.is_private
        withdraw_msg = (
            "💰 **سیستم برداشت**\n\n"
            f"💎 موجودی شما: {user.get('tron', 0):,.0f} ترون\n"
            f"📊 برداشت امروز: {user.get('daily_withdrawn_today', 0):,.0f} / {Config.DAILY_WITHDRAW_LIMIT:,.0f} ترون\n"
            f"🏦 کل برداشت‌ها: {user.get('total_withdrawn', 0):,.0f} ترون\n\n"
            "⚠️ **قوانین برداشت:**\n"
            f"• حد مجاز روزانه: {Config.DAILY_WITHDRAW_LIMIT:,.0f} ترون\n"
            f"• مالیات برداشت: {int(Config.WITHDRAW_TAX*100)}%\n"
            f"• حداقل برداشت: {Config.MIN_BET} ترون\n\n"
            "مبلغ مورد نظر برای برداشت را وارد کنید:"
        )
        if is_private:
            await message.reply(withdraw_msg)
        else:
            await message.reply(withdraw_msg)
        await self.set_user_state(user_id, {"step": "waiting_for_withdraw_amount"},group_id=message.chat_id)
    async def handle_withdraw(self, message: Message, user_id: str, amount: float):
        if amount < Config.MIN_BET:
            await message.reply(f"❌ حداقل برداشت {Config.MIN_BET} ترون است!")
            return
        success, msg, withdrawn_amount = await self.db.withdraw_tron(user_id, amount)
        if success:
            response = (
                f"{msg}\n\n"
                f"💸 مبلغ خالص دریافت: {withdrawn_amount:.2f} ترون\n"
                f"🏦 کد تراکنش: TX{random.randint(10000, 99999)}"
            )
        else:
            response = msg
        if message.is_private:
            await message.reply(response, chat_keypad=self.build_main_keypad())
        else:
            await message.reply(response)
        await self.clear_user_state(user_id)
    async def show_increase_limit_menu(self, message: Message, user_id: str):
        user = await self.db.get_user(user_id)
        is_private = message.is_private
        limit_msg = (
            "📈 **افزایش محدودیت شرط روزانه**\n\n"
            f"🎯 محدودیت فعلی: {user.get('max_bets_per_day', Config.MAX_DAILY_BETS)} شرط در روز\n"
            f"📊 شرط‌های امروز: {user.get('daily_bets_today', 0)}\n"
            f"⭐ سطح VIP: {user.get('vip_level', 0)}\n\n"
            f"💰 هزینه افزایش {Config.MAX_BETS_INCREASE_AMOUNT} واحد: {Config.MAX_BETS_INCREASE_COST:,.0f} ترون\n\n"
            f"برای افزایش محدودیت، '{Config.MAX_BETS_INCREASE_COST:,.0f}' ترون از حساب شما کسر می‌شود."
        )
        if is_private:
            keypad = (
                ChatKeypadBuilder()
                .row(
                    ChatKeypadBuilder().button(id="confirm_increase", text="✅ تایید افزایش"),
                    ChatKeypadBuilder().button(id="cancel_increase", text="❌ انصراف"),
                )
                .row(ChatKeypadBuilder().button(id="back", text="🔙 بازگشت"))
                .build()
            )
            await message.reply(limit_msg, chat_keypad=keypad)
        else:
            await message.reply(limit_msg + "\n\nبرای تایید بنویس: 'تایید افزایش'")
            await self.set_user_state(user_id, {"step": "waiting_for_confirm_increase"},group_id=message.chat_id)
    async def handle_limit_increase(self, message: Message, user_id: str):
        success, msg = await self.db.increase_max_bets(user_id)
        if success:
            user = await self.db.get_user(user_id)
            response = (
                f"{msg}\n\n"
                f"🎯 محدودیت جدید: {user.get('max_bets_per_day')} شرط در روز\n"
                f"⭐ سطح VIP جدید: {user.get('vip_level')}\n"
                f"💰 موجودی جدید: {user.get('tron', 0):,.0f} ترون"
            )
        else:
            response = msg
        if message.is_private:
            await message.reply(response, chat_keypad=self.build_main_keypad())
        else:
            await message.reply(response)
        await self.clear_user_state(user_id)
    async def handle_game_choice(self, message: Message, user_id: str, game_type: str, group_id: str = None):
        state = await self.get_user_state(user_id, group_id)
        if not state or state.get("step") not in ["waiting_for_game_choice", "waiting_for_game_number"]:
            await message.reply("❌ لطفاً اول شرط‌بندی را شروع کنید!")
            return
        bet_amount = state.get("bet_amount", 0)
        multiplier = state.get("multiplier", 1)
        state["game_type"] = game_type
        await self.set_user_state(user_id, state, group_id)
        if game_type in ["dice_game", "blackjack_game", "poker_game", "hokm_game", "slot_game"]:
            if game_type == "dice_game":
                await self.play_dice_game(message, user_id, bet_amount, multiplier, group_id)
            elif game_type == "blackjack_game":
                await self.play_blackjack_game(message, user_id, bet_amount, multiplier, group_id)
            elif game_type == "poker_game":
                await self.play_poker_game(message, user_id, bet_amount, multiplier, group_id)
            elif game_type == "hokm_game":
                await self.play_hokm_game(message, user_id, bet_amount, multiplier, group_id)
            elif game_type == "slot_game":
                await self.play_slot_game(message, user_id, bet_amount, multiplier, group_id)
        else:
            if game_type == "number_game":
                await message.reply("🔢 یک عدد بین 0 تا 10 حدس بزن:")
                await self.set_user_state(user_id, {
                    **state,
                    "step": "waiting_for_number"
                }, group_id)
            elif game_type == "rps_game":
                await message.reply("✂️ سنگ، کاغذ یا قیچی؟")
                await self.set_user_state(user_id, {
                    **state,
                    "step": "waiting_for_rps"
                }, group_id)
    async def play_dice_game(self, message: Message, user_id: str, bet_amount: float, multiplier: float, group_id: str = None):
        won, win_amount, game_data = await self.game_engine.play_dice(bet_amount, multiplier)
        is_draw = game_data.get("result") == "draw"
        await self.finish_bet(message, user_id, won, win_amount, game_data, group_id, is_draw)
    async def play_number_game(self, message: Message, user_id: str, user_input: str, group_id: str = None):
        state = await self.get_user_state(user_id, group_id)
        if not state:
            return
        bet_amount = state.get("bet_amount", 0)
        multiplier = state.get("multiplier", 1)
        user_number = self.game_engine.parse_amount(user_input)
        if user_number is None or user_number < 0 or user_number > 10:
            await message.reply("❌ لطفاً عددی بین 0 تا 10 وارد کنید!")
            return
        won, win_amount, game_data = await self.game_engine.play_number_guess(
            int(user_number), bet_amount, multiplier
        )
        await self.finish_bet(message, user_id, won, win_amount, game_data, group_id)
    async def play_rps_game(self, message: Message, user_id: str, user_choice: str, group_id: str = None):
        state = await self.get_user_state(user_id, group_id)
        if not state:
            return
        bet_amount = state.get("bet_amount", 0)
        multiplier = state.get("multiplier", 1)
        won, win_amount, game_data = await self.game_engine.play_rock_paper_scissors(
            user_choice, bet_amount, multiplier
        )
        is_draw = game_data.get("result") == "draw"
        await self.finish_bet(message, user_id, won, win_amount, game_data, group_id, is_draw)
    async def play_blackjack_game(self, message: Message, user_id: str, bet_amount: float, multiplier: float, group_id: str = None):
        won, win_amount, game_data = await self.game_engine.play_blackjack(bet_amount, multiplier)
        is_draw = game_data.get("result") == "مساوی"
        await self.finish_bet(message, user_id, won, win_amount, game_data, group_id, is_draw)
    async def play_poker_game(self, message: Message, user_id: str, bet_amount: float, multiplier: float, group_id: str = None):
        won, win_amount, game_data = await self.game_engine.play_poker(bet_amount, multiplier)
        await self.finish_bet(message, user_id, won, win_amount, game_data, group_id)
    async def play_hokm_game(self, message: Message, user_id: str, bet_amount: float, multiplier: float, group_id: str = None):
        won, win_amount, game_data = await self.game_engine.play_hokm(bet_amount, multiplier)
        await self.finish_bet(message, user_id, won, win_amount, game_data, group_id)
    async def play_slot_game(self, message: Message, user_id: str, bet_amount: float, multiplier: float, group_id: str = None):
        won, win_amount, game_data = await self.game_engine.play_slot(bet_amount, multiplier)
        await self.finish_bet(message, user_id, won, win_amount, game_data, group_id)
    async def start_betting(self, message: Message, user_id: str, group_id: str = None):
        can_bet, error_msg = await self.db.can_user_bet(user_id)
        if not can_bet:
            await message.reply(error_msg)
            return
        user = await self.db.get_user(user_id)
        if user.get("tron", 0) < Config.MIN_BET:
            await message.reply(
                f"❌ موجودی شما کافی نیست!\n"
                f"💰 موجودی: {user.get('tron', 0):,.0f} ترون\n"
                f"🔢 حداقل شرط: {Config.MIN_BET} ترون"
            )
            return
        is_private = message.is_private
        response = (
            "🎰 **سیستم شرط‌بندی پیشرفته**\n\n"
            f"💰 موجودی شما: {user.get('tron', 0):,.0f} ترون\n"
            f"📊 شرط‌های امروز: {user.get('daily_bets_today', 0)}/{user.get('max_bets_per_day', Config.MAX_DAILY_BETS)}\n\n"
            "لطفاً مقدار شرط را وارد کنید (مثلاً: 200 یا ۱۵۰.۵):\n"
            f"⚠️ حداقل: {Config.MIN_BET} ترون\n"
            f"⚠️ حداکثر: {Config.MAX_BET} ترون"
        )
        if is_private:
            await message.reply(response, chat_keypad=self.build_main_keypad())
        else:
            await message.reply(response)
        await self.set_user_state(user_id, {
            "step": "waiting_for_bet_amount"
        }, group_id)
    async def process_bet_step(self, message: Message, user_id: str, text: str, group_id: str = None):
        state = await self.get_user_state(user_id, group_id)
        step = state.get("step")
        if step == "waiting_for_bet_amount":
            bet_amount = self.game_engine.parse_amount(text)
            user = await self.db.get_user(user_id)
            if not bet_amount or bet_amount <= 0:
                await message.reply("❌ مقدار نامعتبر! لطفاً یک عدد وارد کنید.")
                return
            is_valid, error_msg = self.game_engine.validate_bet(
                bet_amount, 1, user.get("tron", 0)
            )
            if not is_valid:
                await message.reply(error_msg)
                return
            await self.set_user_state(user_id, {
                **state,
                "step": "waiting_for_multiplier",
                "bet_amount": bet_amount
            }, group_id)
            await message.reply(
                f"✅ شرط {bet_amount:,.0f} ترون ثبت شد!\n\n"
                f"📊 ضریب شرط را وارد کنید ({Config.MIN_MULTIPLIER} تا {Config.MAX_MULTIPLIER}):\n"
                f"مثال: 2 یا ۱.۵ یا ۱۰.۷۵\n"
                f"⚠️ ضریب بالاتر = ریسک بیشتر = سود بیشتر"
            )
        elif step == "waiting_for_multiplier":
            multiplier = self.game_engine.parse_amount(text)
            bet_amount = state.get("bet_amount", 0)
            user = await self.db.get_user(user_id)
            if not multiplier or multiplier < Config.MIN_MULTIPLIER:
                await message.reply(f"❌ ضریب نامعتبر! حداقل {Config.MIN_MULTIPLIER}")
                return
            is_valid, error_msg = self.game_engine.validate_bet(
                bet_amount, multiplier, user.get("tron", 0)
            )
            if not is_valid:
                await message.reply(error_msg)
                return
            success, new_balance = await self.db.deduct_tron(user_id, bet_amount)
            if not success:
                await message.reply(f"❌ خطا در کسر ترون! موجودی: {new_balance:,.0f}")
                await self.clear_user_state(user_id, group_id)
                return
            await self.db.increment_daily_bet(user_id)
            await self.set_user_state(user_id, {
                **state,
                "step": "waiting_for_game_number",
                "bet_amount": bet_amount,
                "multiplier": multiplier,
                "user_balance": new_balance
            }, group_id)
            is_private = message.is_private
            response = (
                f"🎉 **شرط شما ثبت شد!**\n\n"
                f"💰 مبلغ: {bet_amount:,.0f} ترون\n"
                f"📊 ضریب: {multiplier}x\n"
                f"💸 سود احتمالی: {bet_amount * multiplier:,.2f} ترون\n"
                f"💎 موجودی جدید: {new_balance:,.0f} ترون\n"
                f"📅 شرط‌های امروز: {user.get('daily_bets_today', 0)+1}/{user.get('max_bets_per_day', Config.MAX_DAILY_BETS)}\n\n"
                f"🎮 **بازی را انتخاب کنید:**"
            )
            if is_private:
                await message.reply(response, chat_keypad=self.build_bet_keypad())
            else:
                games_list = (
                    "\n\n🎮 **لیست بازی‌ها:**\n"
                    "1️⃣ **اعداد** - عدد بین 0 تا 10\n"
                    "2️⃣ **سنگ کاغذ قیچی** - سنگ، کاغذ یا قیچی\n"
                    "3️⃣ **تاس** - پرتاب تاس\n"
                    "4️⃣ **بلک‌جک** - بازی 21\n"
                    "5️⃣ **پوکر** - دست‌های پوکر\n"
                    "6️⃣ **حکم** - بازی ورق ایرانی\n"
                    "7️⃣ **اسلات** - ماشین اسلات\n\n"
                    "شماره بازی مورد نظر را بنویسید (1 تا 7):"
                )
                await message.reply(response + games_list)
                await self.set_user_state(user_id, {
                    **state,
                    "step": "waiting_for_game_number",
                    "bet_amount": bet_amount,
                    "multiplier": multiplier,
                    "user_balance": new_balance
                }, group_id)
    async def finish_bet(self, message: Message, user_id: str, won: bool, win_amount: float, game_data: Dict, group_id: str = None, is_draw: bool = False):
        state = await self.get_user_state(user_id, group_id)
        if not state:
            return
        bet_amount = state.get("bet_amount", 0)
        bet_id = str(uuid.uuid4())[:8]
        if won:
            new_balance = await self.db.add_tron(user_id, win_amount)
            result_text = f"🎉 **برنده شدی!**\n💰 سود شما: {win_amount:,.2f} ترون"
            result_emoji = "🎊"
        elif win_amount > 0 or is_draw:
            new_balance = await self.db.add_tron(user_id, win_amount)
            result_text = f"🤝 **مساوی!**\n💸 مبلغ شرط بازگشت داده شد: {win_amount:,.0f} ترون"
            result_emoji = "🤝"
        else:
            new_balance = state.get("user_balance", 0)
            result_text = f"😔 **باختی!**\n💸 مبلغ شرط از دست رفت: {bet_amount:,.0f} ترون"
            result_emoji = "😢"
        await self.db.add_bet(bet_id, {
            "user_id": user_id,
            "group_id": group_id,
            "bet_amount": bet_amount,
            "multiplier": state.get("multiplier", 1),
            "won": won,
            "win_amount": win_amount if won else 0,
            "game_data": game_data,
            "final_balance": new_balance
        })
        await self.db.update_user_stats(user_id, won, bet_amount, win_amount if won else 0, is_draw)
        await self.clear_user_state(user_id, group_id)
        result_msg = f"{result_emoji} **نتیجه شرط #{bet_id}**\n\n"
        game_type = game_data.get("game")
        if game_type == "blackjack":
            result_msg += (
                f"🎮 **بازی:** بلک‌جک\n"
                f"🃏 کارت‌های شما: {', '.join(game_data.get('user_cards', []))}\n"
                f"🔢 امتیاز شما: {game_data.get('user_score')}\n"
                f"🃏 کارت‌های دیلر: {', '.join(game_data.get('dealer_cards', []))}\n"
                f"🔢 امتیاز دیلر: {game_data.get('dealer_score')}\n"
            )
        elif game_type == "poker":
            result_msg += (
                f"🎮 **بازی:** پوکر\n"
                f"🎴 دست شما: {game_data.get('user_hand')}\n"
                f"🎴 دست ربات: {game_data.get('bot_hand')}\n"
            )
        elif game_type == "hokm":
            result_msg += (
                f"🎮 **بازی:** حکم\n"
                f"♠️ حکم: {game_data.get('hokm')}\n"
                f"🃏 کارت‌های شما: {', '.join(game_data.get('user_cards', []))}\n"
                f"💪 قدرت دست شما: {game_data.get('user_power')}\n"
            )
        elif game_type == "slot":
            result_msg += f"🎮 **بازی:** اسلات\n"
            result_msg += game_data.get("slot_display", "")
            if game_data.get("winning_lines"):
                result_msg += f"🎯 خطوط برنده: {len(game_data['winning_lines'])}\n"
        elif game_type == "number_guess":
            result_msg += (
                f"🎮 **بازی:** حدس عدد\n"
                f"🔢 حدس شما: {game_data.get('user_number')}\n"
                f"🤖 عدد ربات: {game_data.get('bot_number')}\n"
            )
        elif game_type == "rock_paper_scissors":
            result_msg += (
                f"🎮 **بازی:** سنگ کاغذ قیچی\n"
                f"✋ انتخاب شما: {game_data.get('user_choice')}\n"
                f"🤖 انتخاب ربات: {game_data.get('bot_choice')}\n"
            )
        elif game_type == "dice":
            result_msg += (
                f"🎮 **بازی:** تاس\n"
                f"🎲 تاس شما: {game_data.get('user_dice')}\n"
                f"🎲 تاس ربات: {game_data.get('bot_dice')}\n"
            )
        result_msg += f"\n{result_text}\n\n"
        result_msg += f"💰 **موجودی جدید:** {new_balance:,.0f} ترون\n"
        user = await self.db.get_user(user_id)
        result_msg += f"📊 **شرط‌های امروز:** {user.get('daily_bets_today', 0)}/{user.get('max_bets_per_day', Config.MAX_DAILY_BETS)}\n"
        if "multiplier" in game_data and game_data["multiplier"]:
            result_msg += f"📈 **ضریب:** {game_data.get('multiplier')}x\n"
        result_msg += f"🕐 **زمان:** {datetime.now().strftime('%H:%M:%S')}"
        is_private = message.is_private
        if is_private:
            await message.reply(result_msg, chat_keypad=self.build_main_keypad())
        else:
            await message.reply(result_msg)
    async def show_profile(self, message: Message, user_id: str):
        await self.db.reset_daily_stats(user_id)
        user = await self.db.get_user(user_id)
        top_users = await self.db.get_top_users(1000)
        rank = next((i+1 for i, u in enumerate(top_users) if u['id'] == user_id), 0)
        total_won = user.get("total_won", 0)
        total_bet = user.get("total_bet", 0)
        net_profit = total_won - total_bet
        profile_msg = (
            f"👤 **پروفایل پیشرفته**\n\n"
            f"** آیدی شما: **\n `{user_id}`\n\n"
            f"👑 **لقب:** {user.get('title', 'تازه‌وارد')}\n"
            f"💰 **ترون:** {user.get('tron', 0):,.0f}\n"
            f"🏆 **رتبه:** #{rank if rank > 0 else 'جدید'}\n"
            f"⭐ **سطح VIP:** {user.get('vip_level', 0)}\n\n"
            f"📊 **آمار بازی:**\n"
            f"✅ بردها: {user.get('wins', 0)}\n"
            f"🤝 مساوی‌ها: {user.get('draws', 0)}\n"
            f"❌ باخت‌ها: {user.get('losses', 0)}\n"
            f"🎰 مجموع شرط: {total_bet:,.0f} ترون\n"
            f"💸 مجموع برد: {total_won:,.0f} ترون\n"
            f"📈 سود خالص: {net_profit:,.0f} ترون\n\n"
            f"📅 **آمار امروز:**\n"
            f"🎯 شرط‌ها: {user.get('daily_bets_today', 0)}/{user.get('max_bets_per_day', Config.MAX_DAILY_BETS)}\n"
            f"💰 برداشت: {user.get('daily_withdrawn_today', 0):,.0f}/{Config.DAILY_WITHDRAW_LIMIT:,.0f} ترون\n\n"
            f"🏦 کل برداشت: {user.get('total_withdrawn', 0):,.0f} ترون\n"
            f"📅 عضویت: {user.get('created_at', '')[:10]}"
        )
        is_private = message.is_private
        if is_private:
            await message.reply(profile_msg, chat_keypad=self.build_main_keypad())
        else:
            await message.reply(profile_msg)
    async def show_shop(self, message: Message, user_id: str):
        user = await self.db.get_user(user_id)
        user_tron = user.get("tron", 0)
        is_private = message.is_private
        shop_msg = (
            "🛒 **فروشگاه لقب‌ها**\n\n"
            f"💰 موجودی شما: {user_tron:,.0f} ترون\n"
            f"👑 لقب فعلی: {user.get('title', 'تازه‌وارد')}\n\n"
            "👇 لیست لقب‌ها:\n\n"
        )
        for title, price in Config.TITLES.items():
            if price > 0:
                can_buy = user_tron >= price
                emoji = "✅" if can_buy else "❌"
                shop_msg += f"{emoji} **{title}** - {price:,.0f} ترون\n"
        shop_msg += f"\n💡 برای خرید بنویس: خرید [لقب]\nمثال: خرید شوالیه"
        if is_private:
            await message.reply(shop_msg, chat_keypad=self.build_shop_keypad(user_tron))
        else:
            await message.reply(shop_msg)
    async def show_leaderboard(self, message: Message, limit: int = 10):
        top_users = await self.db.get_top_users(limit)
        if not top_users:
            await message.reply("📭 هنوز کاربری در جدول وجود ندارد!")
            return
        leaderboard_msg = "🏆 **جدول برترین‌ها** 🏆\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for idx, user in enumerate(top_users):
            if idx < len(medals):
                medal = medals[idx]
            else:
                medal = f"{idx+1}."
            win_rate = 0
            total_games = user.get('wins', 0) + user.get('losses', 0) + user.get('draws', 0)
            if total_games > 0:
                win_rate = (user.get('wins', 0) / total_games) * 100
            leaderboard_msg += (
                f"{medal} **{user.get('title', 'تازه‌وارد')}**\n"
                f"   👤 آیدی: `{user['id'][:8]}...`\n"
                f"   💰 ترون: {user.get('tron', 0):,.0f}\n"
                f"   📊 برد/مس/باخت: {user.get('wins', 0)}/{user.get('draws', 0)}/{user.get('losses', 0)}\n"
                f"   📈 درصد برد: {win_rate:.1f}%\n\n"
            )
        await message.reply(leaderboard_msg)
    async def handle_admin_command(self, message: Message, command: str, args: str):
        user_id = str(message.sender_id)
        if not await self.db.is_admin(user_id):
            await message.reply("❌ شما دسترسی ادمین ندارید!")
            return
        parts = args.split()
        if command == "add_tron":
            if len(parts) >= 2:
                target_user = parts[0]
                amount = self.game_engine.parse_amount(parts[1])
                if amount and amount > 0:
                    new_balance = await self.db.add_tron(target_user, amount)
                    await message.reply(
                        f"✅ {amount:,.0f} ترون به کاربر {target_user} اضافه شد!\n"
                        f"💰 موجودی جدید: {new_balance:,.0f} ترون"
                    )
                else:
                    await message.reply("❌ مقدار نامعتبر!")
            else:
                await message.reply("فرمت صحیح:\n`/add_tron [آیدی] [مقدار]`")
        elif command == "remove_tron":
            if len(parts) >= 2:
                target_user = parts[0]
                amount = self.game_engine.parse_amount(parts[1])
                if amount and amount > 0:
                    success, new_balance = await self.db.deduct_tron(target_user, amount)
                    if success:
                        await message.reply(
                            f"✅ {amount:,.0f} ترون از کاربر {target_user} کسر شد!\n"
                            f"💰 موجودی جدید: {new_balance:,.0f} ترون"
                        )
                    else:
                        await message.reply("❌ موجودی کاربر کافی نیست!")
                else:
                    await message.reply("❌ مقدار نامعتبر!")
            else:
                await message.reply("فرمت صحیح:\n`/remove_tron [آیدی] [مقدار]`")
        elif command == "user_stats":
            if len(parts) >= 1:
                target_user = parts[0]
                user = await self.db.get_user(target_user)
                stats_msg = (
                    f"📊 **آمار کاربر {target_user}**\n\n"
                    f"👑 لقب: {user.get('title', 'تازه‌وارد')}\n"
                    f"💰 ترون: {user.get('tron', 0):,.0f}\n"
                    f"🏆 بردها: {user.get('wins', 0)}\n"
                    f"💀 باخت‌ها: {user.get('losses', 0)}\n"
                    f"🤝 مساوی‌ها: {user.get('draws', 0)}\n"
                    f"🎰 مجموع شرط: {user.get('total_bet', 0):,.0f} ترون\n"
                    f"💸 مجموع برد: {user.get('total_won', 0):,.0f} ترون\n"
                    f"📅 عضویت از: {user.get('created_at', 'نامشخص')}"
                )
                await message.reply(stats_msg)
            else:
                await message.reply("فرمت صحیح:\n`/user_stats [آیدی]`")
        elif command == "set_admin":
            if len(parts) >= 1:
                target_user = parts[0]
                await self.db.update_user(target_user, {"role": "admin"})
                await message.reply(f"✅ کاربر {target_user} ادمین شد!")
            else:
                await message.reply("فرمت صحیح:\n`/set_admin [آیدی]`")
        elif command == "remove_admin":
            if len(parts) >= 1:
                target_user = parts[0]
                await self.db.update_user(target_user, {"role": "user"})
                await message.reply(f"✅ کاربر {target_user} از ادمینی حذف شد!")
            else:
                await message.reply("فرمت صحیح:\n`/remove_admin [آیدی]`")
        elif command == "reset_stats":
            if len(parts) >= 1:
                target_user = parts[0]
                await self.db.update_user(target_user, {
                    "wins": 0,
                    "losses": 0,
                    "draws": 0,
                    "total_bet": 0,
                    "total_won": 0
                })
                await message.reply(f"✅ آمار کاربر {target_user} بازنشانی شد!")
            else:
                await message.reply("فرمت صحیح:\n`/reset_stats [آیدی]`")
    async def handle_button_click(self, message: Message, user_id: str, callback: str, group_id: str = None):
        if callback == "start_bet":
            await self.start_betting(message, user_id, group_id)
        elif callback == "profile":
            await self.show_profile(message, user_id)
        elif callback == "leaderboard":
            await self.show_leaderboard(message)
        elif callback == "shop":
            await self.show_shop(message, user_id)
        elif callback == "withdraw":
            await self.show_withdraw_menu(message, user_id)
        elif callback == "increase_limit":
            await self.show_increase_limit_menu(message, user_id)
        elif callback == "confirm_increase":
            await self.handle_limit_increase(message, user_id)
        elif callback == "cancel_increase":
            await message.reply("❌ افزایش محدودیت لغو شد.", chat_keypad=self.build_main_keypad())
        elif callback in ["blackjack_game", "poker_game", "hokm_game", "slot_game", "dice_game", "number_game", "rps_game"]:
            game_map = {
                "blackjack_game": "blackjack_game",
                "poker_game": "poker_game",
                "hokm_game": "hokm_game",
                "slot_game": "slot_game",
                "dice_game": "dice_game",
                "number_game": "number_game",
                "rps_game": "rps_game"
            }
            game_type = game_map.get(callback)
            if game_type:
                await self.handle_game_choice(message, user_id, game_type, group_id)
        elif callback == "help":
            await message.reply(
                "❓ **راهنمای ربات پیشرفته**\n\n"
                "🎰 **بازی‌های جدید:**\n"
                "• 🃏 بلک‌جک: بازی 21 معروف\n"
                "• 🎴 پوکر: دست‌های پوکر\n"
                "• ♠️ حکم: بازی ورق ایرانی\n"
                "• 🎰 اسلات: ماشین اسلات\n\n"
                "💰 **سیستم برداشت:**\n"
                f"• حد مجاز روزانه: {Config.DAILY_WITHDRAW_LIMIT:,.0f} ترون\n"
                f"• مالیات برداشت: {int(Config.WITHDRAW_TAX*100)}%\n\n"
                "📊 **محدودیت شرط:**\n"
                f"• شروع: {Config.MAX_DAILY_BETS} شرط در روز\n"
                f"• افزایش: {Config.MAX_BETS_INCREASE_COST:,.0f} ترون برای {Config.MAX_BETS_INCREASE_AMOUNT} شرط بیشتر\n\n"
                "👑 **لقب‌های بیشتر:**\n"
                "با ترون بیشتر، لقب‌های بالاتر بگیرید!\n"
                "🔹 برای دیدن همه‌ی دستورات و آموزش‌ها به کانال زیر برو:\n"
                f"📢 {CHANNEL_MAIN}\n"
            )
        elif callback == "back":
            await message.reply("🔙 **منوی اصلی**", chat_keypad=self.build_main_keypad())
        elif callback == "cancel_bet":
            state = await self.get_user_state(user_id, group_id)
            if state and state.get("step") == "waiting_for_game_choice":
                bet_amount = state.get("bet_amount", 0)
                if bet_amount > 0:
                    await self.db.add_tron(user_id, bet_amount)
                    await message.reply(f"✅ شرط لغو شد! {bet_amount:,.0f} ترون بازگشت.")
                await self.clear_user_state(user_id, group_id)
            else:
                await message.reply("❌ شرط فعالی برای لغو وجود ندارد!")
        elif callback.startswith("buy_"):
            title = callback[4:]
            if title in Config.TITLES:
                price = Config.TITLES[title]
                user = await self.db.get_user(user_id)
                if user.get("tron", 0) >= price:
                    success, new_balance = await self.db.deduct_tron(user_id, price)
                    if success:
                        await self.db.update_user(user_id, {"title": title})
                        await message.reply(
                            f"🎉 لقب **{title}** خریداری شد!\n"
                            f"💰 هزینه: {price:,.0f} ترون\n"
                            f"💎 موجودی جدید: {new_balance:,.0f} ترون",
                            chat_keypad=self.build_main_keypad()
                        )
                    else:
                        await message.reply("❌ خطا در پردازش خرید!", chat_keypad=self.build_main_keypad())
                else:
                    await message.reply(f"❌ موجودی کافی نیست! قیمت: {price:,.0f} ترون", chat_keypad=self.build_main_keypad())
        elif callback == "btn_join":
            guid_channel = GUID_CHANNEL
            guid_channel_espanser = GUID_CHANNEL_SPONSOR
            try:
                if await self.bot.check_join(
                    channel_guid=guid_channel, chat_id=message.chat_id
                ) and await self.bot.check_join(
                    channel_guid=guid_channel_espanser, chat_id=message.chat_id
                ):
                    self.chat_db.add_chat(message.chat_id)
                    user = await self.db.get_user(user_id)
                    await message.reply(
                        f"🎰 **به ربات شرط‌بندی پیشرفته خوش آمدید!**\n\n"
                        f"👋 سلام {user.get('title', 'کاربر')}!\n"
                        f"💰 موجودی: {user.get('tron', 0):,.0f} ترون\n"
                        f"🎯 محدودیت شرط: {user.get('max_bets_per_day', Config.MAX_DAILY_BETS)} در روز\n\n"
                        "🆕 **بازی‌های جدید:**\n"
                        "• 🃏 بلک‌جک\n• 🎴 پوکر\n• ♠️ حکم\n• 🎰 اسلات\n\n"
                        "👇 از منوی زیر انتخاب کنید:",
                        chat_keypad=self.build_main_keypad()
                    )
                    return
                else:
                    name = await self.bot.get_name(chat_id=message.chat_id)
                    await message.reply(
                        f"سلام {name} 👋\nشما عضو کانال نیستید ❌\n {CHANNEL_MAIN}\n{CHANNEL_SECOND}\n و دکمه عضو شدم رو بزنید"
                    )
            except Exception as e:
                print(e)
    async def setup_handlers(self):
        @self.bot.on_message_private(filters=filters.is_text)
        async def private_handler(bot: Robot, message: Message):
            user_id = str(message.sender_id)
            text = message.text.strip() if message.text else ""
            callback = message.aux_data.button_id if message.aux_data else None
            if callback:
                await self.handle_button_click(message, user_id, callback)
                return
            if text.startswith("/"):
                parts = text[1:].split(maxsplit=1)
                command = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                if command in ["add_tron", "remove_tron", "user_stats", "set_admin", "remove_admin", "reset_stats"]:
                    await self.handle_admin_command(message, command, args)
                    return
            state = await self.get_user_state(user_id)
            if state:
                step = state.get("step")
                if step == "waiting_for_withdraw_amount":
                    amount = self.game_engine.parse_amount(text)
                    if amount:
                        await self.handle_withdraw(message, user_id, amount)
                    else:
                        await message.reply("❌ مبلغ نامعتبر!")
                    return
                elif step in ["waiting_for_bet_amount", "waiting_for_multiplier"]:
                    await self.process_bet_step(message, user_id, text)
                    return
                elif step == "waiting_for_number":
                    await self.play_number_game(message, user_id, text)
                    return
                elif step == "waiting_for_rps":
                    await self.play_rps_game(message, user_id, text)
                    return
            if text.startswith("خرید ") and len(text) > 5:
                title_to_buy = text[5:].strip()
                if title_to_buy in Config.TITLES:
                    price = Config.TITLES[title_to_buy]
                    user = await self.db.get_user(user_id)
                    if user.get("tron", 0) >= price:
                        success, new_balance = await self.db.deduct_tron(user_id, price)
                        if success:
                            await self.db.update_user(user_id, {"title": title_to_buy})
                            await message.reply(
                                f"🎉 لقب **{title_to_buy}** خریداری شد!\n"
                                f"💰 هزینه: {price:,.0f} ترون\n"
                                f"💎 موجودی جدید: {new_balance:,.0f} ترون",
                                chat_keypad=self.build_main_keypad()
                            )
                        else:
                            await message.reply("❌ خطا در پردازش خرید!", chat_keypad=self.build_main_keypad())
                    else:
                        await message.reply(f"❌ موجودی کافی نیست! قیمت: {price:,.0f} ترون", chat_keypad=self.build_main_keypad())
                else:
                    await message.reply("❌ لقب مورد نظر یافت نشد!", chat_keypad=self.build_main_keypad())
            elif text == "/start":
                if not self.chat_db.has_chat(message.chat_id):
                    join_button = (
                        ChatKeypadBuilder()
                        .row(
                            ChatKeypadBuilder().button(id="btn_join", text="✅ عضو شدم")
                        )
                        .build()
                    )
                    await message.reply(
                        text=f"لطفاً ابتدا عضو کانال‌های رسمی ما شوید تا از ربات استفاده کنید.\n {CHANNEL_MAIN}\n{CHANNEL_SECOND}",
                        chat_keypad=join_button
                        )
                else:
                    user = await self.db.get_user(user_id)
                    await message.reply(
                        f"🎰 **به ربات شرط‌بندی پیشرفته خوش آمدید!**\n\n"
                        f"👋 سلام {user.get('title', 'کاربر')}!\n"
                        f"💰 موجودی: {user.get('tron', 0):,.0f} ترون\n"
                        f"🎯 محدودیت شرط: {user.get('max_bets_per_day', Config.MAX_DAILY_BETS)} در روز\n\n"
                        "🆕 **بازی‌های جدید:**\n"
                        "• 🃏 بلک‌جک\n• 🎴 پوکر\n• ♠️ حکم\n• 🎰 اسلات\n\n"
                        "👇 از منوی زیر انتخاب کنید:",
                        chat_keypad=self.build_main_keypad()
                    )
                if text in ["پروفایل", "/profile"]:
                    await self.show_profile(message, user_id)
                elif text in ["جدول", "/leaderboard"]:
                    await self.show_leaderboard(message)
                elif text in ["فروشگاه", "/shop"]:
                    await self.show_shop(message, user_id)
                elif text in ["برداشت", "/withdraw"]:
                    await self.show_withdraw_menu(message, user_id)
                elif text in ["محدودیت", "/limit"]:
                    await self.show_increase_limit_menu(message, user_id)
                elif text in ["شروع", "شرط", "/bet"]:
                    await self.start_betting(message, user_id)
                elif text in ["راهنما", "/help"]:
                    await message.reply(
                        "🎰 **ربات شرط‌بندی پیشرفته ترون**\n\n"
                        "**بازی‌ها:**\n"
                        "🔢 اعداد | ✂️ سنگ کاغذ قیچی | 🎲 تاس\n"
                        "🃏 بلک‌جک | 🎴 پوکر | ♠️ حکم | 🎰 اسلات\n\n"
                        "**امکانات جدید:**\n"
                        "💰 سیستم برداشت با مالیات\n"
                        "📊 محدودیت شرط روزانه\n"
                        "📈 افزایش محدودیت با پرداخت\n"
                        "👑 12 سطح لقب\n\n"
                        "**دستورات:**\n"
                        "پروفایل - آمار شما\n"
                        "جدول - برترین‌ها\n"
                        "فروشگاه - خرید لقب\n"
                        "برداشت - برداشت ترون\n"
                        "محدودیت - افزایش محدودیت\n"
                        "شرط - شروع شرط‌بندی\n\n"
                        "**دستورات ادمین:**\n"
                        "/add_tron [آیدی] [مقدار]\n"
                        "/remove_tron [آیدی] [مقدار]\n"
                        "/user_stats [آیدی]\n"
                        "/set_admin [آیدی]\n"
                        "/remove_admin [آیدی]\n"
                        "/reset_stats [آیدی]\n"
                        "🔹 برای دیدن همه‌ی دستورات و آموزش‌ها به کانال زیر برو:\n"
                        f"📢 {CHANNEL_MAIN}\n"
                    )
        @self.bot.on_message_group(filters=filters.is_text)
        async def group_handler(bot: Robot, message: Message):
            user_id = str(message.sender_id)
            group_id = str(message.chat_id)
            text = message.text.strip() if message.text else ""
            if text.startswith("/"):
                parts = text[1:].split(maxsplit=1)
                command = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                if await self.db.is_admin(user_id):
                    if command in ["add_tron", "remove_tron", "user_stats", "set_admin", "remove_admin", "reset_stats"]:
                        await self.handle_admin_command(message, command, args)
                        return
            state = await self.get_user_state(user_id, group_id)
            if state:
                step = state.get("step")
                if step == "waiting_for_withdraw_amount":
                    amount = self.game_engine.parse_amount(text)
                    if amount:
                        await self.handle_withdraw(message, user_id, amount)
                    else:
                        await message.reply("❌ مبلغ نامعتبر!")
                    return
                elif step == "waiting_for_confirm_increase":
                    if text in ["تایید افزایش", "بله", "آره"]:
                        await self.handle_limit_increase(message, user_id)
                    else:
                        await message.reply("❌ افزایش محدودیت لغو شد.")
                    await self.clear_user_state(user_id, group_id)
                    return
                elif step == "waiting_for_game_number":
                    game_map = {
                        "1": "number_game",
                        "2": "rps_game",
                        "3": "dice_game",
                        "4": "blackjack_game",
                        "5": "poker_game",
                        "6": "hokm_game",
                        "7": "slot_game"
                    }
                    game_type = game_map.get(text)
                    if game_type:
                        await self.handle_game_choice(message, user_id, game_type, group_id)
                    else:
                        await message.reply("❌ شماره بازی نامعتبر! عدد ۱ تا ۷ وارد کنید.")
                    return
                elif step in ["waiting_for_bet_amount", "waiting_for_multiplier"]:
                    await self.process_bet_step(message, user_id, text, group_id)
                    return
                elif step == "waiting_for_number":
                    await self.play_number_game(message, user_id, text, group_id)
                    return
                elif step == "waiting_for_rps":
                    await self.play_rps_game(message, user_id, text, group_id)
                    return
            if text.startswith("خرید ") and len(text) > 5:
                title_to_buy = text[5:].strip()
                if title_to_buy in Config.TITLES:
                    price = Config.TITLES[title_to_buy]
                    user = await self.db.get_user(user_id)
                    if user.get("tron", 0) >= price:
                        success, new_balance = await self.db.deduct_tron(user_id, price)
                        if success:
                            await self.db.update_user(user_id, {"title": title_to_buy})
                            await message.reply(
                                f"🎉 لقب **{title_to_buy}** خریداری شد!\n"
                                f"💰 هزینه: {price:,.0f} ترون\n"
                                f"💎 موجودی جدید: {new_balance:,.0f} ترون"
                            )
                        else:
                            await message.reply("❌ خطا در پردازش خرید!")
                    else:
                        await message.reply(f"❌ موجودی کافی نیست! قیمت: {price:,.0f} ترون")
                else:
                    await message.reply("❌ لقب مورد نظر یافت نشد!")
                return
            if text in ["شروع", "شرط", "/bet"]:
                await self.start_betting(message, user_id, group_id)
            elif text in ["پروفایل", "/profile"]:
                await self.show_profile(message, user_id)
            elif text in ["جدول", "/leaderboard"]:
                await self.show_leaderboard(message)
            elif text in ["فروشگاه", "/shop"]:
                await self.show_shop(message, user_id)
            elif text in ["برداشت", "/withdraw"]:
                await self.show_withdraw_menu(message, user_id)
            elif text in ["محدودیت", "/limit"]:
                await self.show_increase_limit_menu(message, user_id)
            elif text in ["راهنما", "/help"]:
                await message.reply(
                    "🎰 **ربات شرط‌بندی ترون**\n\n"
                    "شروع - شروع شرط‌بندی\n"
                    "پروفایل - نمایش پروفایل\n"
                    "جدول - جدول برترین‌ها\n"
                    "فروشگاه - خرید لقب\n"
                    "برداشت - برداشت ترون\n"
                    "محدودیت - افزایش محدودیت\n\n"
                    "خرید لقب: خرید [نام لقب]\nمثال: خرید شوالیه\n"
                    "🔹 برای دیدن همه‌ی دستورات و آموزش‌ها به کانال زیر برو:\n"
                    f"📢 {CHANNEL_MAIN}\n"
                )
            elif text in ["بازی‌ها", "games"]:
                await message.reply(
                    "🎮 **لیست بازی‌ها:**\n"
                    "1️⃣ اعداد\n"
                    "2️⃣ سنگ کاغذ قیچی\n"
                    "3️⃣ تاس\n"
                    "4️⃣ بلک‌جک\n"
                    "5️⃣ پوکر\n"
                    "6️⃣ حکم\n"
                    "7️⃣ اسلات\n\n"
                    "برای بازی ابتدا 'شروع' را بنویسید."
                )
    async def run(self):
        await self.db.initialize()
        await self.setup_handlers()
        print("=" * 50)
        print("🤖 ربات شرط‌بندی ترون - نسخه پیشرفته")
        print(f"📊 کاربران: {len(self.db.users)}")
        print(f"🎮 بازی‌های جدید: بلک‌جک، پوکر، حکم، اسلات")
        print(f"💰 سیستم برداشت با مالیات {int(Config.WITHDRAW_TAX*100)}%")
        print(f"📈 محدودیت شرط: {Config.MAX_DAILY_BETS} در روز")
        print("=" * 50)
        print("✅ ربات آماده اجراست!")
        print("=" * 50)
        await self.bot.run()
if __name__ == "__main__":
    if Config.BOT_TOKEN == "TOKEN_HERE":
        print("❌ لطفاً توکن ربات خود را قرار دهید!")
        print("📝 در Config.BOT_TOKEN یا متغیر محیطی TRON_BOT_TOKEN")
        exit(1)
    try:
        from rubka.asynco import Robot
    except ImportError:
        print("❌ کتابخانه rubka-asynco نصب نشده است!")
        print("📦 pip install rubka-asynco aiofiles")
        exit(1)
    bot = TronBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n👋 ربات متوقف شد!")
    except Exception as e:
        print(f"❌ خطا: {e}")