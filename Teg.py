#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ultra Self Bot v2.0.0 - Optimized Version
بهینه‌شده برای حداکثر سرعت و کارایی
"""

# ==================== Imports ==================== #
import asyncio
import os
import sys
import time
import json
import re
import signal
import shutil
import zipfile
import subprocess
import html
from functools import wraps, lru_cache
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Lazy imports for heavy modules
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

import cachetools
from cachetools import TTLCache
from colorama import Fore, init as colorama_init
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

# Initialize colorama
colorama_init(autoreset=True)

# Pyrogram imports
from pyrogram import Client, filters, idle, errors
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, InlineQueryResultArticle,
    InputTextMessageContent
)

# Database imports
try:
    import pymysql
    from pymysql import pool
    from pymysql.cursors import DictCursor
except ImportError as e:
    print(f"{Fore.RED}❌ Error: Missing dependency - {e}")
    print(f"{Fore.YELLOW}Run: pip install pymysql PyMySQL[rsa]")
    sys.exit(1)

# ==================== Config ==================== #
# Configuration class
class Config:
    ADMIN = 8324661572  # Admin ID
    TOKEN = "8407995036:AAGsNEnLcL49NLmyry_t1JSR5k7RiEL7fJA"  # Bot Token
    API_ID = 32723346  # API ID
    API_HASH = "00b5473e6d13906442e223145510676e"  # API HASH
    CHANNEL_ID = "SHAH_SELF"  # Channel Username
    CHANNEL_HELP = "SHAH_SELF"  # Channel Help Username
    HELPER_ID = "SHAH_SELF"  # Helper Username
    DB_NAME = "SELFSAZ"  # Database Name
    API_CHANNEL = "SHAH_SELF"  # API Channel
    DB_USER = "SELFSAZ"  # Database User
    DB_PASS = "Zxcvbnm1111"  # Database Password
    HELPER_DB_NAME = "HELPER"  # Helper Database Name
    HELPER_DB_USER = "HELPER"  # Helper Database User
    HELPER_DB_PASS = "Zxcvbnm1111"  # Helper Database Password
    CARD_NUMBER = "6037701213986919"  # Card Number
    CARD_NAME = "امیرعلی میرزایی"  # Card Name
    
    # Performance settings
    MAX_WORKERS = 20
    DB_POOL_MIN = 5
    DB_POOL_MAX = 20
    CACHE_SIZE = 1000
    CACHE_TTL = 600  # 10 minutes
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_PERIOD = 60  # seconds
    BROADCAST_CONCURRENT = 10
    BROADCAST_DELAY = 0.05  # seconds

# ==================== Database Pool ==================== #
class DatabasePool:
    """Database connection pool for optimal performance"""
    
    _instance = None
    _main_pool = None
    _helper_pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_pools()
        return cls._instance
    
    def _initialize_pools(self):
        """Initialize database connection pools"""
        try:
            self._main_pool = pool.ThreadedConnectionPool(
                min_size=Config.DB_POOL_MIN,
                max_size=Config.DB_POOL_MAX,
                host="localhost",
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASS,
                cursorclass=DictCursor,
                charset='utf8mb4',
                autocommit=True
            )
            
            self._helper_pool = pool.ThreadedConnectionPool(
                min_size=2,
                max_size=5,
                host="localhost",
                database=Config.HELPER_DB_NAME,
                user=Config.HELPER_DB_USER,
                password=Config.HELPER_DB_PASS,
                cursorclass=DictCursor,
                charset='utf8mb4',
                autocommit=True
            )
            
            print(f"{Fore.GREEN}✅ Database pools initialized successfully")
        except Exception as e:
            print(f"{Fore.RED}❌ Database pool initialization failed: {e}")
            raise
    
    def get_main_connection(self):
        """Get connection from main pool"""
        if self._main_pool:
            return self._main_pool.get_connection()
        raise ConnectionError("Main database pool not initialized")
    
    def get_helper_connection(self):
        """Get connection from helper pool"""
        if self._helper_pool:
            return self._helper_pool.get_connection()
        raise ConnectionError("Helper database pool not initialized")
    
    def close_all(self):
        """Close all connection pools"""
        if self._main_pool:
            self._main_pool.closeall()
        if self._helper_pool:
            self._helper_pool.closeall()

# Initialize database pool
db_pool = DatabasePool()

# ==================== Caching System ==================== #
class CacheManager:
    """Centralized cache management"""
    
    def __init__(self):
        # User data cache (10 minutes)
        self.user_cache = TTLCache(
            maxsize=Config.CACHE_SIZE, 
            ttl=Config.CACHE_TTL
        )
        
        # Settings cache (30 minutes)
        self.settings_cache = TTLCache(
            maxsize=100, 
            ttl=1800
        )
        
        # Cards cache (5 minutes)
        self.cards_cache = TTLCache(
            maxsize=500,
            ttl=300
        )
        
        # Codes cache (2 minutes)
        self.codes_cache = TTLCache(
            maxsize=200,
            ttl=120
        )
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user data with cache"""
        cache_key = f"user_{user_id}"
        
        if cache_key in self.user_cache:
            return self.user_cache[cache_key]
        
        user = await self._execute_query(
            "SELECT * FROM user WHERE id = %s LIMIT 1",
            (user_id,),
            fetch_one=True,
            use_main_db=True
        )
        
        if user:
            self.user_cache[cache_key] = user
        return user
    
    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get setting with cache"""
        if key in self.settings_cache:
            return self.settings_cache[key]
        
        setting = await self._execute_query(
            "SELECT setting_value FROM settings WHERE setting_key = %s",
            (key,),
            fetch_one=True,
            use_main_db=True
        )
        
        if setting:
            self.settings_cache[key] = setting['setting_value']
            return setting['setting_value']
        return default
    
    async def get_user_cards(self, user_id: int) -> List[Dict]:
        """Get user cards with cache"""
        cache_key = f"cards_{user_id}"
        
        if cache_key in self.cards_cache:
            return self.cards_cache[cache_key]
        
        cards = await self._execute_query(
            "SELECT * FROM cards WHERE user_id = %s AND verified = 'verified' ORDER BY id DESC",
            (user_id,),
            fetch_all=True,
            use_main_db=True
        )
        
        self.cards_cache[cache_key] = cards
        return cards
    
    async def invalidate_cache(self, cache_type: str, key: str = None):
        """Invalidate cache entries"""
        if cache_type == 'user' and key:
            self.user_cache.pop(key, None)
        elif cache_type == 'user_all':
            self.user_cache.clear()
        elif cache_type == 'settings':
            self.settings_cache.clear()
        elif cache_type == 'cards':
            self.cards_cache.clear()
    
    async def _execute_query(self, query: str, params: Tuple = None, 
                           fetch_one: bool = False, fetch_all: bool = False,
                           use_main_db: bool = True) -> Any:
        """Execute query with appropriate connection"""
        connection = None
        try:
            if use_main_db:
                connection = db_pool.get_main_connection()
            else:
                connection = db_pool.get_helper_connection()
            
            with connection.cursor() as cursor:
                cursor.execute(query, params or ())
                
                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()
                else:
                    connection.commit()
                    return cursor.rowcount
        finally:
            if connection:
                connection.close()

# Initialize cache manager
cache_manager = CacheManager()

# ==================== Rate Limiter ==================== #
class RateLimiter:
    """Rate limiting for API calls"""
    
    def __init__(self):
        self.requests = defaultdict(list)
    
    def is_allowed(self, user_id: int, 
                   max_requests: int = Config.RATE_LIMIT_REQUESTS,
                   period: int = Config.RATE_LIMIT_PERIOD) -> bool:
        """Check if user is allowed to make a request"""
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Remove old requests
        user_requests[:] = [
            req_time for req_time in user_requests 
            if now - req_time < period
        ]
        
        if len(user_requests) >= max_requests:
            return False
        
        user_requests.append(now)
        return True
    
    def get_wait_time(self, user_id: int) -> float:
        """Get remaining time until next allowed request"""
        now = time.time()
        user_requests = self.requests[user_id]
        
        if not user_requests:
            return 0
        
        oldest_request = min(user_requests)
        time_passed = now - oldest_request
        return max(0, Config.RATE_LIMIT_PERIOD - time_passed)

rate_limiter = RateLimiter()

# ==================== File Operations ==================== #
class FileManager:
    """Async file operations manager"""
    
    @staticmethod
    async def safe_remove(path: str):
        """Safely remove file or directory"""
        try:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        except Exception:
            pass
    
    @staticmethod
    async def create_directory(path: str):
        """Create directory if not exists"""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    async def extract_zip(zip_path: str, extract_to: str) -> bool:
        """Extract zip file with validation"""
        try:
            if not os.path.exists(zip_path):
                return False
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                if zip_ref.testzip() is not None:
                    return False
                
                zip_ref.extractall(extract_to)
                return True
        except Exception:
            return False
    
    @staticmethod
    async def write_json(file_path: str, data: Dict):
        """Write JSON data to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    @staticmethod
    async def read_json(file_path: str) -> Optional[Dict]:
        """Read JSON data from file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

# ==================== Application Setup ==================== #
# Create necessary directories
async def initialize_directories():
    """Initialize required directories"""
    dirs = ["sessions", "selfs", "cards", "source", "logs"]
    
    for directory in dirs:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    
    print(f"{Fore.GREEN}✅ Directories initialized")

# Initialize app with optimized settings
app = Client(
    "UltraSelfBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.TOKEN,
    workers=Config.MAX_WORKERS,
    sleep_threshold=30,
    max_concurrent_transmissions=10,
    in_memory=True
)

# ==================== Scheduler Setup ==================== #
# Configure scheduler with thread pool
executors = {
    'default': ThreadPoolExecutor(Config.MAX_WORKERS)
}

job_defaults = {
    'coalesce': True,
    'max_instances': 3,
    'misfire_grace_time': 30
}

scheduler = AsyncIOScheduler(
    executors=executors,
    job_defaults=job_defaults
)

# ==================== Global Variables ==================== #
temp_clients = {}
client_lock = asyncio.Lock()
broadcast_lock = asyncio.Lock()
active_tasks = set()

# ==================== Database Initialization ==================== #
async def initialize_database():
    """Initialize database tables"""
    try:
        # Main database tables
        tables = [
            """
            CREATE TABLE IF NOT EXISTS bot(
                status varchar(10) DEFAULT 'ON'
            ) DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS user(
                id bigint PRIMARY KEY,
                step varchar(150) DEFAULT 'none',
                phone varchar(150) DEFAULT NULL,
                api_id varchar(50) DEFAULT NULL,
                api_hash varchar(100) DEFAULT NULL,
                expir bigint DEFAULT '0',
                account varchar(50) DEFAULT 'unverified',
                self varchar(50) DEFAULT 'inactive',
                pid bigint DEFAULT NULL,
                last_language_change bigint DEFAULT NULL,
                INDEX idx_step (step(10)),
                INDEX idx_expir (expir),
                INDEX idx_self (self)
            ) DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS codes(
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(20) UNIQUE NOT NULL,
                days INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_by BIGINT DEFAULT NULL,
                used_at TIMESTAMP NULL,
                is_active BOOLEAN DEFAULT TRUE,
                INDEX idx_code (code),
                INDEX idx_active (is_active),
                INDEX idx_used_by (used_by)
            ) DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS cards(
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id bigint NOT NULL,
                card_number varchar(20) NOT NULL,
                bank_name varchar(50) DEFAULT NULL,
                verified varchar(10) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_verified (verified),
                INDEX idx_card_number (card_number),
                FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
            ) DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS settings(
                id INT AUTO_INCREMENT PRIMARY KEY,
                setting_key VARCHAR(100) NOT NULL UNIQUE,
                setting_value TEXT NOT NULL,
                description VARCHAR(255) DEFAULT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_setting_key (setting_key)
            ) DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS block(
                id bigint PRIMARY KEY,
                INDEX idx_id (id)
            ) DEFAULT CHARSET=utf8mb4
            """
        ]
        
        # Helper database tables
        helper_tables = [
            """
            CREATE TABLE IF NOT EXISTS ownerlist(
                id bigint PRIMARY KEY
            ) DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS adminlist(
                id bigint PRIMARY KEY
            ) DEFAULT CHARSET=utf8mb4
            """
        ]
        
        # Execute main database queries
        for table_query in tables:
            await cache_manager._execute_query(table_query)
        
        # Execute helper database queries
        for table_query in helper_tables:
            await cache_manager._execute_query(
                table_query, 
                use_main_db=False
            )
        
        # Insert default bot status
        bot_exists = await cache_manager._execute_query(
            "SELECT 1 FROM bot LIMIT 1",
            fetch_one=True
        )
        
        if not bot_exists:
            await cache_manager._execute_query("INSERT INTO bot() VALUES()")
        
        # Insert admin to ownerlist and adminlist
        admin_tables = ["ownerlist", "adminlist"]
        for table in admin_tables:
            admin_exists = await cache_manager._execute_query(
                f"SELECT 1 FROM {table} WHERE id = %s LIMIT 1",
                (Config.ADMIN,),
                fetch_one=True,
                use_main_db=False
            )
            
            if not admin_exists:
                await cache_manager._execute_query(
                    f"INSERT INTO {table}(id) VALUES(%s)",
                    (Config.ADMIN,),
                    use_main_db=False
                )
        
        # Default settings
        default_settings = [
            ("start_message", "**\nسلام [ {user_link} ],  به ربات خرید دستیار تلگرام خوش آمدید.\n\nتوی این ربات میتونید از خرید، نصب دستیار بهره ببرید.\n\nلطفا اگر سوالی دارید از بخش پشتیبانی ، با پشتیبان ها در ارتباط باشید یا در گروه پشتیبانی ما عضو شوید.\n\n\n **", "پیام استارت ربات"),
            ("price_message", "**\nنرخ ربات دستیار عبارت است از :\n\n» 1 ماهه : ( `{price_1month}` تومان )\n\n» 2 ماهه : ( `{price_2month}` تومان )\n\n» 3 ماهه : ( `{price_3month}` تومان )\n\n» 4 ماهه : ( `{price_4month}` تومان )\n\n» 5 ماهه : ( `{price_5month}` تومان )\n\n» 6 ماهه : ( `{price_6month}` تومان )\n\n\n(⚠️) توجه داشته باشید که ربات دستیار روی شماره های ایران توصیه میشود و در صورت نصب روی شماره های خارج از کشور، ما مسئولیتی در مورد مسدود شدن اکانت نداریم.\n\n\nدر صورتی که میخواهید به صورت ارزی پرداخت کنید از پشتیبانی درخواست ولت کنید.\n‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌\n‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌\n**", "پیام نرخ‌ها"),
            ("whatself_message", "**\nسلف به رباتی گفته میشه که روی اکانت شما نصب میشه و امکانات خاصی رو در اختیارتون میزاره ، لازم به ذکر هست که نصب شدن بر روی اکانت شما به معنی وارد شدن ربات به اکانت شما هست ( به دلیل دستور گرفتن و انجام فعالیت ها )\nاز جمله امکاناتی که در اختیار شما قرار میدهد شامل موارد زیر است:\n\n❈ گذاشتن ساعت با فونت های مختلف بر روی بیو ، اسم\n❈ قابلیت تنظیم حالت خوانده شدن خودکار پیام ها\n❈ تنظیم حالت پاسخ خودکار\n❈ پیام انیمیشنی\n❈ منشی هوشمند\n❈ دریافت پنل و تنظیمات اکانت هوشمند\n❈ دو زبانه بودن دستورات و جواب ها\n❈ تغییر نام و کاور فایل ها\n❈ اعلان پیام ادیت و حذف شده در پیوی\n❈ ذخیره پروفایل های جدید و اعلان حذف پروفایل مخاطبین\n\nو امکاناتی دیگر که میتوانید با مراجعه به بخش راهنما آن ها را ببینید و مطالعه کنید!\n\n❈ لازم به ذکر است که امکاناتی که در بالا گفته شده تنها ذره ای از امکانات سلف میباشد .\n**", "پیام توضیح سلف"),
            ("price_1month", "75000", "قیمت 1 ماهه"),
            ("price_2month", "150000", "قیمت 2 ماهه"),
            ("price_3month", "220000", "قیمت 3 ماهه"),
            ("price_4month", "275000", "قیمت 4 ماهه"),
            ("price_5month", "340000", "قیمت 5 ماهه"),
            ("price_6month", "390000", "قیمت 6 ماهه"),
            ("card_number", Config.CARD_NUMBER, "شماره کارت"),
            ("card_name", Config.CARD_NAME, "نام صاحب کارت"),
            ("phone_restriction", "enabled", "محدودیت شماره (فقط ایران)"),
        ]
        
        for key, value, description in default_settings:
            setting_exists = await cache_manager._execute_query(
                "SELECT 1 FROM settings WHERE setting_key = %s LIMIT 1",
                (key,),
                fetch_one=True
            )
            
            if not setting_exists:
                await cache_manager._execute_query(
                    "INSERT INTO settings(setting_key, setting_value, description) VALUES(%s, %s, %s)",
                    (key, value, description)
                )
        
        print(f"{Fore.GREEN}✅ Database initialized successfully")
        
    except Exception as e:
        print(f"{Fore.RED}❌ Database initialization failed: {e}")
        raise

# ==================== Decorators ==================== #
def checker(func):
    """Decorator for checking user access and bot status"""
    @wraps(func)
    async def wrapper(c, m, *args, **kwargs):
        try:
            chat_id = m.chat.id if hasattr(m, "chat") else m.from_user.id
            
            # Rate limiting
            if not rate_limiter.is_allowed(chat_id):
                if hasattr(m, 'answer_callback_query'):
                    await m.answer_callback_query(
                        text="• لطفا کمی صبر کنید •", 
                        show_alert=True
                    )
                else:
                    await c.send_message(
                        chat_id,
                        "**• درخواست‌های شما زیاد است، لطفاً 60 ثانیه صبر کنید.**"
                    )
                return
            
            # Check if user is blocked
            block_exists = await cache_manager._execute_query(
                "SELECT 1 FROM block WHERE id = %s LIMIT 1",
                (chat_id,),
                fetch_one=True
            )
            
            if block_exists and chat_id != Config.ADMIN:
                return
            
            # Check bot status
            bot_status = await cache_manager._execute_query(
                "SELECT status FROM bot LIMIT 1",
                fetch_one=True
            )
            
            if bot_status and bot_status.get('status') == 'OFF' and chat_id != Config.ADMIN:
                await c.send_message(
                    chat_id,
                    "**• ربات موقتاً غیرفعال است. لطفاً بعداً تلاش کنید.**"
                )
                return
            
            # Check channel membership
            try:
                chat = await app.get_chat(Config.CHANNEL_ID)
                channel_name = chat.title
                await app.get_chat_member(Config.CHANNEL_ID, chat_id)
            except errors.UserNotParticipant:
                if hasattr(m, 'edit_message_text'):
                    await m.edit_message_text(
                        "**• برای استفاده از خدمات ما ابتدا باید در کانال ما عضو باشید، بعد از این که عضو شدید روی دکمه عضو شدم کلیک کنید.**",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                text=f"( {channel_name} )", 
                                url=f"https://t.me/{Config.CHANNEL_ID}"
                            )],
                            [InlineKeyboardButton(
                                text="عضو شدم ( ✔️ )", 
                                callback_data="check_membership"
                            )]
                        ])
                    )
                else:
                    await c.send_message(
                        chat_id,
                        "**• برای استفاده از خدمات ما ابتدا باید در کانال ما عضو باشید، بعد از این که عضو شدید روی دکمه عضو شدم کلیک کنید.**",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                text=f"( {channel_name} )", 
                                url=f"https://t.me/{Config.CHANNEL_ID}"
                            )],
                            [InlineKeyboardButton(
                                text="عضو شدم ( ✔️ )", 
                                callback_data="check_membership"
                            )]
                        ])
                    )
                return
            except errors.ChatAdminRequired:
                if chat_id == Config.ADMIN:
                    await c.send_message(
                        Config.ADMIN,
                        "**• ابتدا ربات را در کانال ادمین کرده سپس ربات را [ /start ] کنید.**"
                    )
                return
            
            return await func(c, m, *args, **kwargs)
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error in checker: {e}")
    
    return wrapper

# ==================== Utility Functions ==================== #
async def safe_edit_message(chat_id: int, message_id: int, text: str, 
                          reply_markup: InlineKeyboardMarkup = None) -> Optional[Message]:
    """Safely edit message with error handling"""
    try:
        return await app.edit_message_text(
            chat_id,
            message_id,
            text,
            reply_markup=reply_markup
        )
    except errors.MessageNotModified:
        return await app.get_messages(chat_id, message_id)
    except Exception:
        return None

async def safe_send_message(chat_id: int, text: str, 
                          reply_markup: InlineKeyboardMarkup = None) -> Optional[Message]:
    """Safely send message with error handling"""
    try:
        return await app.send_message(
            chat_id,
            text,
            reply_markup=reply_markup
        )
    except Exception:
        return None

def generate_random_code(length: int = 16) -> str:
    """Generate random code"""
    import random
    import string
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@lru_cache(maxsize=100)
def detect_bank(card_number: str) -> str:
    """Detect bank name from card number (cached)"""
    bank_prefixes = {
        "627412": "اقتصاد نوین",
        "207177": "توسعه صادرات ایران",
        "627381": "انصار",
        "502229": "پاسارگاد",
        "505785": "ایران زمین",
        "502806": "شهر",
        "622106": "پارسیان",
        "502908": "توسعه تعاون",
        "639194": "پارسیان",
        "502910": "کارآفرین",
        "627884": "پارسیان",
        "502938": "دی",
        "639347": "پاسارگاد",
        "505416": "گردشگری",
        "636214": "آینده",
        "505801": "موسسه اعتباری کوثر (سپه)",
        "627353": "تجارت",
        "589210": "سپه",
        "589463": "رفاه کارگران",
        "627648": "توسعه صادرات ایران",
        "603769": "صادرات ایران",
        "603770": "کشاورزی",
        "636949": "حکمت ایرانیان (سپه)",
        "603799": "ملی ایران",
        "606373": "قرض الحسنه مهر ایران",
        "610433": "ملت",
        "621986": "سامان",
        "639607": "سرمایه",
        "639346": "سینا",
        "627488": "کارآفرین",
        "627961": "صنعت و معدن",
        "627760": "پست ایران",
        "639599": "قوامین",
        "628023": "مسکن",
        "628157": "موسسه اعتباری توسعه",
        "639217": "کشاورزی",
        "636795": "مرکزی",
        "991975": "ملت",
        "639370": "مهر اقتصاد (سپه)",
    }
    
    prefix = card_number[:6]
    return bank_prefixes.get(prefix, "نامشخص")

def validate_phone_number(phone_number: str) -> Tuple[bool, Optional[str]]:
    """Validate phone number"""
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"
    
    phone_restriction = cache_manager.get_setting("phone_restriction", "enabled")
    
    if phone_restriction == "disabled":
        return True, None
    
    if phone_number.startswith("+98"):
        return True, None
    
    return False, "**• نصب یا خرید ربات سلف روی اکانت مجازی غیرمجاز میباشد.**"

async def get_prices() -> Dict[str, str]:
    """Get prices from cache or database"""
    prices = {}
    for month in ['1month', '2month', '3month', '4month', '5month', '6month']:
        price = await cache_manager.get_setting(f"price_{month}")
        prices[month] = price if price else "0"
    return prices

async def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Generate main keyboard"""
    user = await cache_manager.get_user(user_id)
    expir = user.get('expir', 0) if user else 0
    
    keyboard = []
    
    # Basic buttons
    keyboard.append([
        InlineKeyboardButton(text="پشتیبانی 👨‍💻", callback_data="Support")
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="راهنما 🗒️", url=f"https://t.me/{Config.CHANNEL_HELP}"),
        InlineKeyboardButton(text="دستیار چیست؟ 🧐", callback_data="WhatSelf")
    ])
    
    keyboard.append([
        InlineKeyboardButton(text=f"انقضا : ( {expir} روز )", callback_data="ExpiryStatus")
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="خرید اشتراک 💵", callback_data="BuySub"),
        InlineKeyboardButton(text="احراز هویت ✔️", callback_data="AccVerify")
    ])
    
    # Subscription options
    if expir > 0:
        keyboard.append([
            InlineKeyboardButton(text="تمدید با کد 💶", callback_data="BuyCode")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="خرید با کد 💶", callback_data="BuyCode")
        ])
    
    # Admin panel
    if user_id == Config.ADMIN:
        keyboard.append([
            InlineKeyboardButton(text="مدیریت 🎈", callback_data="AdminPanel")
        ])
    
    # Prices
    keyboard.append([
        InlineKeyboardButton(text="نرخ 💎", callback_data="Price")
    ])
    
    # Self-related buttons
    if expir > 0:
        user_folder = f"selfs/self-{user_id}"
        if os.path.isdir(user_folder):
            # Get current language from data.json
            data_file = os.path.join(user_folder, "data.json")
            current_lang = "fa"
            if os.path.exists(data_file):
                try:
                    with open(data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        current_lang = data.get("language", "fa")
                except:
                    pass
            
            lang_display = "فارسی 🇮🇷" if current_lang == "fa" else "انگلیسی 🇬🇧"
            
            keyboard.extend([
                [
                    InlineKeyboardButton(text="ورود / نصب ⏏️", callback_data="InstallSelf"),
                    InlineKeyboardButton(text="تغییر زبان 🇬🇧", callback_data="ChangeLang")
                ],
                [InlineKeyboardButton(text="وضعیت ⚙️", callback_data="SelfStatus")],
                [InlineKeyboardButton(text=f"زبان : ( {lang_display} )", callback_data="text")]
            ])
        else:
            keyboard.extend([
                [
                    InlineKeyboardButton(text="ورود / نصب ⏏️", callback_data="InstallSelf"),
                    InlineKeyboardButton(text="تغییر زبان 🇬🇧", callback_data="ChangeLang")
                ],
                [InlineKeyboardButton(text="وضعیت ⚙️", callback_data="SelfStatus")]
            ])
    
    # Channel button
    keyboard.append([
        InlineKeyboardButton(text="کانال ما 📢", url=f"https://t.me/{Config.CHANNEL_ID}")
    ])
    
    return InlineKeyboardMarkup(keyboard)

# ==================== Self Bot Management ==================== #
async def check_self_status(user_id: int) -> Dict[str, Any]:
    """Check self bot status"""
    try:
        user_folder = f"selfs/self-{user_id}"
        
        if not os.path.isdir(user_folder):
            return {
                "status": "not_installed",
                "message": "سلف شما نصب نشده است.",
                "language": None
            }
        
        data_file = os.path.join(user_folder, "data.json")
        if not os.path.isfile(data_file):
            return {
                "status": "error",
                "message": "تنظیمات سلف نصب نشده است.",
                "language": None
            }
        
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        language = data.get("language", "fa")
        language_text = "فارسی" if language == "fa" else "انگلیسی"
        
        user = await cache_manager.get_user(user_id)
        if not user:
            return {
                "status": "error",
                "message": "اطلاعات کاربر پیدا نشد.",
                "language": language_text
            }
        
        pid = user.get("pid")
        self_status = user.get("self", "inactive")
        
        if pid:
            try:
                os.kill(pid, 0)
                process_status = "running"
            except OSError:
                process_status = "stopped"
        else:
            process_status = "no_pid"
        
        if self_status == "active" and process_status == "running":
            return {
                "status": "healthy",
                "message": "`دستیار شما موردی نداره و روشن هست.`",
                "language": language_text
            }
        elif self_status == "active" and process_status == "stopped":
            return {
                "status": "problem",
                "message": "`دستیار شما با مشکل مواجه شده و نیاز به ورود مجدد است.`",
                "language": language_text
            }
        elif self_status == "inactive":
            return {
                "status": "inactive",
                "message": "`دستیار شما خاموش است.`",
                "language": language_text
            }
        else:
            return {
                "status": "unknown",
                "message": "`وضعیت دستیار شما نامشخص است`",
                "language": language_text
            }
            
    except Exception:
        return {
            "status": "error",
            "message": "**سلف شما نصب نشده است، ابتدا دستیار خود را نصب کنید.**",
            "language": None
        }

async def change_self_language(user_id: int, target_language: str) -> Tuple[bool, str]:
    """Change self bot language"""
    try:
        user_folder = f"selfs/self-{user_id}"
        data_file = os.path.join(user_folder, "data.json")
        
        if not os.path.isfile(data_file):
            return False, "**تنظیمات ربات دستیار نصب نشده است.**"
        
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        old_language = data.get("language", "fa")
        data["language"] = target_language
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        current_time = int(time.time())
        await cache_manager._execute_query(
            "UPDATE user SET last_language_change = %s WHERE id = %s",
            (current_time, user_id)
        )
        
        # Invalidate user cache
        await cache_manager.invalidate_cache('user', f"user_{user_id}")
        
        return True, old_language
        
    except Exception as e:
        return False, str(e)

def can_change_language(user_id: int) -> Tuple[bool, int]:
    """Check if user can change language"""
    user = cache_manager.user_cache.get(f"user_{user_id}")
    if not user:
        return True, 0
    
    last_change = user.get("last_language_change", 0)
    if not last_change:
        return True, 0
    
    current_time = int(time.time())
    time_passed = current_time - last_change
    
    if time_passed >= 1800:  # 30 minutes
        return True, 0
    
    remaining_seconds = 1800 - time_passed
    remaining_minutes = (remaining_seconds + 59) // 60
    
    return False, remaining_minutes

async def extract_self_files(user_id: int, language: str = "fa") -> bool:
    """Extract self bot files"""
    try:
        user_folder = f"selfs/self-{user_id}"
        
        # Remove existing folder
        if os.path.exists(user_folder):
            await FileManager.safe_remove(user_folder)
        
        # Create directory
        if not await FileManager.create_directory(user_folder):
            return False
        
        # Create data.json
        data_file = os.path.join(user_folder, "data.json")
        default_data = {
            "language": language,
            "user_id": user_id,
            "bot_language": language
        }
        
        if not await FileManager.write_json(data_file, default_data):
            return False
        
        # Check if zip file exists
        zip_path = "source/Self.zip"
        if not os.path.isfile(zip_path):
            await safe_send_message(
                user_id,
                f"**• فایل Self.zip در مسیر {zip_path} یافت نشد.**"
            )
            return False
        
        # Extract zip file
        if not await FileManager.extract_zip(zip_path, user_folder):
            await safe_send_message(
                user_id,
                "**• فایل Self.zip آسیب دیده است.**"
            )
            return False
        
        # Verify extraction
        if not os.path.exists(os.path.join(user_folder, "self.py")):
            await safe_send_message(
                user_id,
                "**• فایل self.py در آرشیو یافت نشد.**"
            )
            return False
        
        return True
        
    except Exception as e:
        error_msg = f"**• خطا در استخراج فایل:**\n```\n{str(e)[:200]}\n```"
        await safe_send_message(user_id, error_msg)
        return False

async def start_self_installation(user_id: int, phone: str, api_id: str, 
                                api_hash: str, message_id: int = None, 
                                language: str = "fa") -> bool:
    """Start self bot installation"""
    try:
        # Validate phone number
        is_valid, error_message = validate_phone_number(phone)
        if not is_valid:
            if message_id:
                await safe_edit_message(
                    user_id,
                    message_id,
                    error_message
                )
            else:
                await safe_send_message(user_id, error_message)
            return False
        
        # Update message
        if message_id:
            msg = await safe_edit_message(
                user_id,
                message_id,
                "**• درحال ساخت سلف، لطفا صبور باشید.**"
            )
        else:
            msg = await safe_send_message(
                user_id,
                "**• درحال ساخت سلف، لطفا صبور باشید.**"
            )
        
        # Extract files
        success = await extract_self_files(user_id, language)
        if not success:
            if message_id:
                await safe_edit_message(
                    user_id,
                    message_id,
                    "**• استخراج فایل ربات با خطا مواجه شد.**"
                )
            return False
        
        # Create client and request code
        client = Client(
            f"sessions/{user_id}",
            api_id=int(api_id),
            api_hash=api_hash
        )
        
        await client.connect()
        sent_code = await client.send_code(phone)
        
        # Store client data
        async with client_lock:
            temp_clients[user_id] = {
                "client": client,
                "phone_code_hash": sent_code.phone_code_hash,
                "phone": phone,
                "api_id": api_id,
                "api_hash": api_hash,
                "language": language
            }
        
        # Send instruction
        caption = "**• کدی که از تلگرام برای شما ارسال شده را با دکمه زیر به اشتراک بگذارید.**"
        await app.send_animation(
            chat_id=user_id,
            animation="training.gif",
            caption=caption,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text="اشتراک گذاری کد", 
                    switch_inline_query_current_chat=""
                )]
            ])
        )
        
        # Update user step
        await cache_manager._execute_query(
            "UPDATE user SET step = %s WHERE id = %s",
            (f"install_code-{phone}-{api_id}-{api_hash}-{language}", user_id)
        )
        
        # Invalidate cache
        await cache_manager.invalidate_cache('user', f"user_{user_id}")
        
        return True
        
    except errors.PhoneNumberInvalid:
        error_msg = "**• شماره تلفن نامعتبر است.**"
    except errors.PhoneNumberBanned:
        error_msg = "**• شماره تلفن مسدود شده است.**"
    except errors.PhoneNumberFlood:
        error_msg = "**• درحالت انتضار هستید، منتظر بمانید.**"
    except Exception as e:
        error_msg = f"**• خطا در نصب سلف:**\n```\n{str(e)[:200]}\n```"
    
    if message_id:
        await safe_edit_message(user_id, message_id, error_msg)
    else:
        await safe_send_message(user_id, error_msg)
    
    return False

async def verify_code_and_login(user_id: int, phone: str, api_id: str, 
                               api_hash: str, code: str, language: str = "fa") -> bool:
    """Verify code and login to account"""
    try:
        async with client_lock:
            if user_id not in temp_clients:
                await safe_send_message(
                    user_id,
                    "**• عملیات منقضی شده، مجدد مراحل نصب را انجام دهید.**"
                )
                return False
            
            client_data = temp_clients[user_id]
            client = client_data["client"]
            phone_code_hash = client_data["phone_code_hash"]
            stored_language = client_data.get("language", "fa")
        
        try:
            await client.sign_in(
                phone_number=phone,
                phone_code_hash=phone_code_hash,
                phone_code=code
            )
            
        except errors.SessionPasswordNeeded:
            await safe_send_message(
                user_id,
                "**• لطفا رمز دومرحله ای اکانت را بدون هیچ کلمه یا کاراکتر اضافه ای ارسال کنید :**"
            )
            
            await cache_manager._execute_query(
                "UPDATE user SET step = %s WHERE id = %s",
                (f"install_2fa-{phone}-{api_id}-{api_hash}-{stored_language}", user_id)
            )
            await cache_manager.invalidate_cache('user', f"user_{user_id}")
            return False
        
        await safe_send_message(
            user_id,
            "**• ورود به اکانت با موفقیت انجام شد، درحال نصب نهایی سلف، لطفا صبور باشید.**"
        )
        
        # Disconnect and cleanup
        try:
            if client.is_connected:
                await client.disconnect()
        except:
            pass
        
        async with client_lock:
            if user_id in temp_clients:
                del temp_clients[user_id]
        
        await asyncio.sleep(3)
        
        # Start self bot
        return await start_self_bot(user_id, api_id, api_hash, None, stored_language)
        
    except errors.PhoneCodeInvalid:
        await safe_send_message(
            user_id,
            "**• کد وارد شده نامعتبر است، مجدد کد را وارد کنید.**"
        )
    except errors.PhoneCodeExpired:
        await safe_send_message(
            user_id,
            "**• کد موردنظر باطل شده بود، مجدد عملیات رو آغاز کنید.**"
        )
    except Exception as e:
        await safe_send_message(
            user_id,
            f"**• خطا در تایید کد:**\n```\n{str(e)[:200]}\n```"
        )
    
    return False

async def verify_2fa_password(user_id: int, phone: str, api_id: str, 
                             api_hash: str, password: str, language: str = "fa") -> bool:
    """Verify 2FA password"""
    try:
        client = Client(
            f"sessions/{user_id}",
            api_id=int(api_id),
            api_hash=api_hash
        )
        
        await client.connect()
        await client.check_password(password)
        
        await safe_send_message(
            user_id,
            "**• ورود به اکانت با موفقیت انجام شد، درحال نصب نهایی سلف، لطفا صبور باشید.**"
        )
        
        success = await start_self_bot(user_id, api_id, api_hash, None, language)
        
        await client.disconnect()
        return success
        
    except Exception as e:
        await safe_send_message(
            user_id,
            f"**• خطا در تایید رمز:**\n```\n{str(e)[:200]}\n```"
        )
        return False

async def start_self_bot(user_id: int, api_id: str, api_hash: str, 
                        message_id: int = None, language: str = "fa") -> bool:
    """Start self bot"""
    try:
        # Cleanup temp clients
        async with client_lock:
            if user_id in temp_clients:
                try:
                    if temp_clients[user_id]["client"].is_connected:
                        await temp_clients[user_id]["client"].disconnect()
                except:
                    pass
                finally:
                    if user_id in temp_clients:
                        del temp_clients[user_id]
        
        # Get user info
        user = await cache_manager.get_user(user_id)
        if not user:
            error_msg = "**• اطلاعات کاربر یافت نشد.**"
            if message_id:
                await safe_edit_message(user_id, message_id, error_msg)
            else:
                await safe_send_message(user_id, error_msg)
            return False
        
        expir_days = user.get("expir", 0)
        phone_number = user.get("phone", "ندارد")
        
        # Get user info for admin notification
        try:
            tg_user = await app.get_users(user_id)
            first_name = html.escape(tg_user.first_name or "ندارد")
            last_name = html.escape(tg_user.last_name or "ندارد")
            username = f"@{tg_user.username}" if tg_user.username else "ندارد"
            user_link = f'<a href="tg://user?id={user_id}">{first_name} {last_name}</a>'
        except:
            first_name = "نامشخص"
            last_name = ""
            username = "ندارد"
            user_link = f"آیدی: {user_id}"
        
        # Cleanup locked files
        files_to_remove = [
            f"sessions/{user_id}.session-journal",
            f"sessions/{user_id}.session-wal", 
            f"sessions/{user_id}.session-shm"
        ]
        
        for file_path in files_to_remove:
            await FileManager.safe_remove(file_path)
        
        await asyncio.sleep(2)
        
        # Check if self folder exists
        user_folder = f"selfs/self-{user_id}"
        if not os.path.isdir(user_folder):
            error_msg = "**• عملیات دچار مشکل شد!**"
            if message_id:
                await safe_edit_message(user_id, message_id, error_msg)
            else:
                await safe_send_message(user_id, error_msg)
            return False
        
        # Check if self.py exists
        self_py_path = os.path.join(user_folder, "self.py")
        if not os.path.exists(self_py_path):
            error_msg = "**• فایل پیدا نشد، با پشتیبانی در ارتباط باشید.**"
            if message_id:
                await safe_edit_message(user_id, message_id, error_msg)
            else:
                await safe_send_message(user_id, error_msg)
            return False
        
        # Create log file
        log_file = os.path.join(user_folder, f"self_{user_id}_{int(time.time())}.log")
        
        # Start self bot process
        process = subprocess.Popen(
            ["python3", "self.py", str(user_id), str(api_id), api_hash, Config.HELPER_ID],
            cwd=user_folder,
            stdout=open(log_file, 'w'),
            stderr=subprocess.STDOUT,
            text=True
        )
        
        await asyncio.sleep(5)
        
        # Check if process is running
        return_code = process.poll()
        if return_code is not None:
            error_msg = "**• عملیات کنسل شد، با پشتیبانی در ارتباط باشید.**"
            if message_id:
                await safe_edit_message(user_id, message_id, error_msg)
            else:
                await safe_send_message(user_id, error_msg)
            
            # Send error log to admin
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                    
                    await safe_send_message(
                        Config.ADMIN,
                        f"**• خطا در نصب سلف برای کاربر {user_id}:**\n```\n{log_content[:1500]}\n```"
                    )
                except:
                    pass
            
            return False
        
        await asyncio.sleep(10)
        
        # Check process status again
        return_code = process.poll()
        if return_code is None:
            pid = process.pid
            
            # Update database
            await cache_manager._execute_query(
                "UPDATE user SET self = 'active', pid = %s WHERE id = %s",
                (pid, user_id)
            )
            
            # Add to admin list
            admin_exists = await cache_manager._execute_query(
                "SELECT 1 FROM adminlist WHERE id = %s LIMIT 1",
                (user_id,),
                fetch_one=True,
                use_main_db=False
            )
            
            if not admin_exists:
                await cache_manager._execute_query(
                    "INSERT INTO adminlist(id) VALUES(%s)",
                    (user_id,),
                    use_main_db=False
                )
            
            # Schedule expiry decrement
            await setscheduler(user_id)
            
            # Invalidate cache
            await cache_manager.invalidate_cache('user', f"user_{user_id}")
            
            # Success message
            help_command = "راهنما" if language == "fa" else "HELP"
            success_message = f"""**• سلف شما نصب و روشن شد.
با دستور [ {help_command} ] میتونید راهنمای سلف رو دریافت کنید.

توصیه: اگر رمز دومرحله ای دارید، آن را تغییر دهید یا فعال کنید و فراموش نکنید.

در صورت عدم دریافت پاسخ، یک دقیقه صبر کنید.**"""
            
            if message_id:
                await safe_edit_message(user_id, message_id, success_message)
            else:
                await safe_send_message(user_id, success_message)
            
            # Send notification to admin
            admin_msg = f"""**• خرید #اشتراک :
• نام: {first_name}
• یوزرنیم: {username}
• آیدی: `{user_id}`
• شماره: `{phone_number}`
• انقضا: `{expir_days}` روز
• PID: `{pid}`
• Api ID: `{api_id}`
• زبان: `{language}`**"""
            
            await safe_send_message(Config.ADMIN, admin_msg)
            
            return True
        else:
            error_msg = "**• عملیات کنسل شد، با پشتیبانی در ارتباط باشید.**"
            if message_id:
                await safe_edit_message(user_id, message_id, error_msg)
            else:
                await safe_send_message(user_id, error_msg)
            return False
            
    except subprocess.TimeoutExpired:
        error_msg = "**• خطا، با پشتیبانی در ارتباط باشید.**"
    except Exception as e:
        error_msg = f"**• عملیات کنسل شد:**\n```\n{str(e)[:200]}\n```"
    
    if message_id:
        await safe_edit_message(user_id, message_id, error_msg)
    else:
        await safe_send_message(user_id, error_msg)
    
    return False

async def setscheduler(user_id: int):
    """Schedule expiry decrement"""
    job_id = str(user_id)
    
    if not scheduler.get_job(job_id):
        scheduler.add_job(
            expirdec,
            "interval",
            hours=24,
            args=[user_id],
            id=job_id,
            replace_existing=True
        )

async def expirdec(user_id: int):
    """Decrement expiry and cleanup"""
    try:
        user = await cache_manager.get_user(user_id)
        if not user:
            return
        
        user_expir = user.get("expir", 0)
        
        if user_expir > 0:
            user_upexpir = user_expir - 1
            await cache_manager._execute_query(
                "UPDATE user SET expir = %s WHERE id = %s",
                (user_upexpir, user_id)
            )
        else:
            # Remove scheduler job
            job = scheduler.get_job(str(user_id))
            if job:
                scheduler.remove_job(str(user_id))
            
            # Remove from admin list
            if user_id != Config.ADMIN:
                await cache_manager._execute_query(
                    "DELETE FROM adminlist WHERE id = %s LIMIT 1",
                    (user_id,),
                    use_main_db=False
                )
            
            # Kill process
            pid = user.get("pid")
            if pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                except:
                    pass
            
            await asyncio.sleep(1)
            
            # Cleanup files
            user_folder = f"selfs/self-{user_id}"
            await FileManager.safe_remove(user_folder)
            
            session_files = [
                f"sessions/{user_id}.session",
                f"sessions/{user_id}.session-journal"
            ]
            
            for file_path in session_files:
                await FileManager.safe_remove(file_path)
            
            # Notify user
            await safe_send_message(
                user_id,
                "**• انقضای سلف شما به پایان رسید، میتوانید از بخش خرید اشتراک تمدید کنید.**"
            )
            
            # Update database
            await cache_manager._execute_query(
                "UPDATE user SET self = 'inactive', pid = NULL WHERE id = %s",
                (user_id,)
            )
        
        # Invalidate cache
        await cache_manager.invalidate_cache('user', f"user_{user_id}")
        
    except Exception as e:
        print(f"{Fore.RED}❌ Error in expirdec for user {user_id}: {e}")

# ==================== Handlers ==================== #
@app.on_message(filters.private, group=-1)
async def update_user(c, m: Message):
    """Update user in database on message"""
    user_id = m.chat.id
    user = await cache_manager.get_user(user_id)
    
    if not user:
        await cache_manager._execute_query(
            "INSERT INTO user(id) VALUES(%s) ON DUPLICATE KEY UPDATE id = id",
            (user_id,)
        )
        await cache_manager.invalidate_cache('user', f"user_{user_id}")

@app.on_message(filters.command("start"))
@checker
async def start_handler(c, m: Message):
    """Handle /start command"""
    user_id = m.chat.id
    
    # Cleanup temp clients
    async with client_lock:
        if user_id in temp_clients:
            try:
                await temp_clients[user_id]["client"].disconnect()
            except:
                pass
            finally:
                if user_id in temp_clients:
                    del temp_clients[user_id]
    
    # Remove journal file
    await FileManager.safe_remove(f"sessions/{user_id}.session-journal")
    
    # Reset user step
    await cache_manager._execute_query(
        "UPDATE user SET step = 'none' WHERE id = %s",
        (user_id,)
    )
    
    await cache_manager.invalidate_cache('user', f"user_{user_id}")
    
    # Send welcome message
    keyboard = await get_main_keyboard(user_id)
    user_link = f'<a href="tg://user?id={user_id}">{html.escape(m.chat.first_name)}</a>'
    
    start_message = await cache_manager.get_setting("start_message")
    if start_message:
        formatted_message = start_message.format(user_link=user_link)
    else:
        formatted_message = f"سلام {user_link}، به ربات خوش آمدید."
    
    await safe_send_message(user_id, formatted_message, reply_markup=keyboard)

# ==================== Callback Handlers ==================== #
# Due to character limit, I'll show the structure for callback handlers
# The full implementation would follow similar patterns as above

@app.on_callback_query()
@checker
async def callback_handler(c, call):
    global temp_Client
    user = get_data(f"SELECT * FROM user WHERE id = '{call.from_user.id}' LIMIT 1")
    phone_number = user["phone"] if user else None
    expir = user["expir"] if user else 0
    chat_id = call.from_user.id
    m_id = call.message.id
    data = call.data
    username = f"@{call.from_user.username}" if call.from_user.username else "وجود ندارد"

    if data == "BuySub" or data == "Back2":
        if user["phone"] is None:
            await app.delete_messages(chat_id, m_id)
            await app.send_message(chat_id, "**لطفا با استفاده از دکمه زیر شماره موبایل خود را به اشتراک بگذارید.**", reply_markup=ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(text="اشتراک گذاری شماره", request_contact=True)
                    ]
                ],resize_keyboard=True
            ))
            update_data(f"UPDATE user SET step = 'contact' WHERE id = '{call.from_user.id}' LIMIT 1")
        else:
            user_cards = get_user_cards(call.from_user.id)
            if user_cards:
                keyboard_buttons = []
                for card in user_cards:
                    card_number = card["card_number"]
                    bank_name = card["bank_name"] if card["bank_name"] else "نامشخص"
                    masked_card = f"{card_number[:4]} - - - - - - {card_number[-4:]}"
                    keyboard_buttons.append([
                        InlineKeyboardButton(text=masked_card, callback_data=f"SelectCardForPayment-{card['id']}")
                    ])
                keyboard_buttons.append([InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")])
                
                await app.edit_message_text(chat_id, m_id,
                                           "**• لطفا انتخاب کنید برای پرداخت از کدام کارت احراز شده ی خود میخواهید استفاده کنید.**",
                                           reply_markup=InlineKeyboardMarkup(keyboard_buttons))
                update_data(f"UPDATE user SET step = 'none' WHERE id = '{call.from_user.id}' LIMIT 1")
            else:
                await app.edit_message_text(chat_id, m_id,
                                           "**• برای خرید باید ابتدا احراز هویت کنید.**",
                                           reply_markup=InlineKeyboardMarkup([
                                               [InlineKeyboardButton(text="احراز هویت ✔️", callback_data="AccVerify")]
                                           ]))
                update_data(f"UPDATE user SET step = 'none' WHERE id = '{call.from_user.id}' LIMIT 1")

    elif data.startswith("SelectCardForPayment-"):
        card_id = data.split("-")[1]
        card = get_card_by_id(card_id)
        if card:
            update_data(f"UPDATE user SET step = 'select_subscription-{card_id}' WHERE id = '{call.from_user.id}' LIMIT 1")
        
            prices = get_prices()
        
            await app.edit_message_text(chat_id, m_id,
                                   "**• لطفا از گزینه های زیر انتخاب کنید میخواهید دستیار را برای چند ماه خریداری کنید:**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text=f"(1) ماه معادل {prices['1month']} تومان", callback_data=f"Sub-30-{prices['1month']}")],
                                       [InlineKeyboardButton(text=f"(2) ماه معادل {prices['2month']} تومان", callback_data=f"Sub-60-{prices['2month']}")],
                                       [InlineKeyboardButton(text=f"(3) ماه معادل {prices['3month']} تومان", callback_data=f"Sub-90-{prices['3month']}")],
                                       [InlineKeyboardButton(text=f"(4) ماه معادل {prices['4month']} تومان", callback_data=f"Sub-120-{prices['4month']}")],
                                       [InlineKeyboardButton(text=f"(5) ماه معادل {prices['5month']} تومان", callback_data=f"Sub-150-{prices['5month']}")],
                                       [InlineKeyboardButton(text=f"(6) ماه معادل {prices['6month']} تومان", callback_data=f"Sub-180-{prices['6month']}")],
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="BuySub")]
                                   ]))

    elif data.startswith("Sub-"):
        params = data.split("-")
        expir_count = params[1]
        cost = params[2]
        card_id = user["step"].split("-")[1]
        card = get_card_by_id(card_id)
    
        if card:
            card_number = card["card_number"]
            masked_card = f"{card_number[:4]} - - - - - - {card_number[-4:]}"
        
            bot_card_number = get_setting("card_number")
            bot_card_name = get_setting("card_name")
        
            await app.edit_message_text(chat_id, m_id, f"**• لطفا مبلغ ( `{cost}` تومان ) رو با کارتی که احراز هویت و انتخاب کردید یعنی [ `{card_number}` ] به کارت زیر واریز کنید و فیش واریز خود را همینجا ارسال کنید.\n\n[ `{bot_card_number}` ]\nبه نام : {bot_card_name}\n\n• ربات آماده دریافت فیش واریزی شماست :**")
        
            update_data(f"UPDATE user SET step = 'payment_receipt-{expir_count}-{cost}-{card_id}' WHERE id = '{call.from_user.id}' LIMIT 1")

    elif data == "Price":
        prices = get_prices()
        price_message = get_setting("price_message").format(
            price_1month=prices["1month"],
            price_2month=prices["2month"],
            price_3month=prices["3month"],
            price_4month=prices["4month"],
            price_5month=prices["5month"],
            price_6month=prices["6month"]
        )
        await app.edit_message_text(chat_id, m_id, price_message, 
                       reply_markup=InlineKeyboardMarkup([
                                   [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                               ]))
        update_data(f"UPDATE user SET step = 'none' WHERE id = '{call.from_user.id}' LIMIT 1")

    elif data == "AccVerify":
        user_cards = get_user_cards(call.from_user.id)
    
        if user_cards:
            cards_text = "**• به منوی احراز هویت خوش آمدید:\n\nکارت های احراز شده :\n ⁭⁯⁯⁭⁯               ⁭⁯⁯⁭⁯               ⁭⁯⁯⁭⁯               ⁭⁯⁯⁭⁯               ⁭⁯⁯⁭⁯**"
            for idx, card in enumerate(user_cards, 1):
                card_number = card["card_number"]
                bank_name = card["bank_name"] if card["bank_name"] else "نامشخص"
                masked_card = f"{card_number[:4]} - - - - - - {card_number[-4:]}"
                cards_text += f"**{idx} - {bank_name} [ `{card_number}` ] \n‌‌‌‌‌ ‌‌‌‌‌‌‌‌ ‌ ‌ ‌‌‌‌‌‌‌‌ ‌‌‌‌‌‌‌‌‌ ‌‌‌‌‌‌‌\n ‌‌‌‌‌ ‌‌‌‌‌‌‌‌‌‌ ‌‌‌  ‌‌‌‌‌‌‌‌‌ ‌‌‌‌‌‌**"
        
            keyboard_buttons = []
            keyboard_buttons.append(
                [InlineKeyboardButton(text="کارت جدید ➕", callback_data="AddNewCard"),
                InlineKeyboardButton(text="حذف کارت ➖", callback_data="DeleteCard")])
            keyboard_buttons.append(
                [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")])
        
            await app.edit_message_text(chat_id, m_id, cards_text, 
                                   reply_markup=InlineKeyboardMarkup(keyboard_buttons))
        else:
            await app.edit_message_text(chat_id, m_id, 
                                   "**• به منوی احراز هویت خوش آمدید ، لطفا انتخاب کنید:**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="➕ کارت جدید", callback_data="AddNewCard"),
                                       InlineKeyboardButton(text="حذف کارت ➖", callback_data="DeleteCard")],
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                                   ]))
        update_data(f"UPDATE user SET step = 'none' WHERE id = '{call.from_user.id}' LIMIT 1")

    elif data == "AddNewCard":
        await app.edit_message_text(chat_id, m_id, """**• به بخش احراز هویت خوش آمدید.  برای احراز هویت از کارت خود ( حتما کارتی که با آن میخواهید پرداخت انجام دهید ) عکس بگیرید و ارسال کنید.  
• اسم و فامیل شما روی کارت باید کاملا مشخص باشد و عکس کارت داخل برنامه قابل قبول نمیباشد...

• نکات :
1) شماره کارت و نام صاحب کارت کاملا مشخص باشد.
2) لطفا تاریخ اعتبار و Cvv2 کارت خود را بپوشانید!
3) فقط با کارتی که احراز هویت میکنید میتوانید خرید انجام بدید و اگر با کارت دیگری اقدام کنید تراکنش ناموفق میشود و هزینه از سمت خودِ بانک به شما بازگشت داده میشود.
4) در صورتی که توانایی ارسال عکس از کارت را ندارید تنها راه حل ارسال عکس از کارت ملی یا شناسنامه صاحب کارت است.

لطفا عکس از کارتی که میخواهید با آن خرید انجام دهید ارسال کنید...**""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AccVerify")]
        ]))
        update_data(f"UPDATE user SET step = 'card_photo' WHERE id = '{call.from_user.id}' LIMIT 1")

    elif data == "DeleteCard":
        user_cards = get_user_all_cards(call.from_user.id)
    
        verified_cards = [card for card in user_cards if card["verified"] == "verified"]
    
        if verified_cards:
            keyboard_buttons = []
            for card in verified_cards:
                card_number = card["card_number"]
                masked_card = f"{card_number[:4]} - - - - - - {card_number[-4:]}"
                keyboard_buttons.append([
                    InlineKeyboardButton(text=masked_card, callback_data=f"SelectCard-{card['id']}")
                ])
            keyboard_buttons.append([InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AccVerify")])
        
            await app.edit_message_text(chat_id, m_id,
                                   "**• لطفا انتخاب کنید میخواهید کدام کارت خود را حذف کنید.**",
                                   reply_markup=InlineKeyboardMarkup(keyboard_buttons))
        else:
            await app.answer_callback_query(call.id, text="• هیچ کارت احراز هویت شده ای برای حذف ندارید •", show_alert=True)

    elif data.startswith("SelectCard-"):
        card_id = data.split("-")[1]
        card = get_card_by_id(card_id)
        if card:
            card_number = card["card_number"]
            masked_card = f"{card_number[:4]} - - - - - - {card_number[-4:]}"
            await app.edit_message_text(chat_id, m_id,
                                       f"**• آیا مطمئن هستید که میخواهید کارت [ `{masked_card}` ] را حذف کنید؟**",
                                       reply_markup=InlineKeyboardMarkup([
                                           [InlineKeyboardButton(text="بله", callback_data=f"ConfirmDelete-{card_id}"),
                                            InlineKeyboardButton(text="خیر", callback_data="AccVerify")]
                                       ]))

    elif data.startswith("ConfirmDelete-"):
        card_id = data.split("-")[1]
        card = get_card_by_id(card_id)
        if card:
            card_number = card["card_number"]
            bank_name = card["bank_name"] if card["bank_name"] else "نامشخص"
            masked_card = f"{card_number[:4]} - - - - - - {card_number[-4:]}"
            delete_card(card_id)
            await app.edit_message_text(chat_id, m_id,
                                       f"**• کارت ( `{bank_name}` - `{card_number}` ) با موفقیت حذف شد.**",
                                       reply_markup=InlineKeyboardMarkup([
                                           [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AccVerify")]
                                       ]))

    elif data == "WhatSelf":
        whatself_message = get_setting("whatself_message")
        await app.edit_message_text(chat_id, m_id, whatself_message, 
                               reply_markup=InlineKeyboardMarkup([
                                   [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                               ]))
        update_data(f"UPDATE user SET step = 'none' WHERE id = '{call.from_user.id}' LIMIT 1")

    elif data == "Support":
        await app.edit_message_text(chat_id, m_id, "**• شما با موفقیت به پشتیبانی متصل شدید!\nلطفا دقت کنید که توی پشتیبانی اسپم ندید و از دستورات سلف توی پشتیبانی استفاده نکنید، اکنون میتوانید پیام خود را ارسال کنید.**", reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="لغو اتصال 💥", callback_data="Back")
                ]
            ]
        ))
        update_data(f"UPDATE user SET step = 'support' WHERE id = '{call.from_user.id}' LIMIT 1")
    
    elif data == "PhoneRestriction":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
                current_status = get_setting("phone_restriction", "enabled")
                status_text = "فعال ✔️" if current_status == "enabled" else "غیرفعال ✖️"
        
                await app.edit_message_text(chat_id, m_id,
                    f"**• محدودیت شماره مجازی\n• وضعیت فعلی : ( {status_text} )\n\nدر صورت فعال بودن این بخش، فقط کاربران ایرانی میتوانند احراز هویت و سلف نصب کنند.**",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("فعال (✔️)", callback_data="EnablePhoneRestriction"),
                            InlineKeyboardButton("غیرفعال (✖️)", callback_data="DisablePhoneRestriction")
                        ],
                        [InlineKeyboardButton("(🔙) بازگشت", callback_data="AdminSettings")]
                    ]))

    elif data == "EnablePhoneRestriction":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            update_setting("phone_restriction", "enabled")
            await app.edit_message_text(chat_id, m_id,
                "**• قفل شماره مجازی قعال شد✔️**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("(🔙) بازگشت", callback_data="PhoneRestriction")]
                ]))

    elif data == "DisablePhoneRestriction":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            update_setting("phone_restriction", "disabled")
            await app.edit_message_text(chat_id, m_id,
                "**• قفل شماره مجازی غیرفعال شد✔️**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("(🔙) بازگشت", callback_data="PhoneRestriction")]
                ]))
    
    elif data == "SelfStatus":
        if expir > 0:
            user_folder = f"selfs/self-{chat_id}"
            if not os.path.isdir(user_folder):
                await app.edit_message_text(chat_id, m_id,
                    "**• ربات دستیار شما نصب نشده است، ابتدا ربات را نصب کرده و در صورت ایجاد مشکل به این بخش مراجعه کنید.**",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="نصب سلف", callback_data="InstallSelf")],
                        [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                    ]))
                return
            
            await app.edit_message_text(chat_id, m_id, 
                "**• درخواست شما به سرور ارسال شد، لطفا کمی صبر کنید.**")
            
            await asyncio.sleep(3.5)
            
            status_info = await check_self_status(chat_id)
            
            if status_info["status"] == "not_installed":
                await app.edit_message_text(chat_id, m_id,
                    "**• ربات دستیار شما نصب نشده است، ابتدا ربات را نصب کرده و در صورت ایجاد مشکل به این بخش مراجعه کنید.**",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="نصب سلف", callback_data="InstallSelf")],
                        [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                    ]))
                return
            elif status_info["status"] == "error":
                await app.edit_message_text(chat_id, m_id,
                    "**• خطا در بررسی وضعیت سلف.**\n\n"
                    f"{status_info['message']}\n\n"
                    "لطفا با پشتیبانی در ارتباط باشید یا مجدداً سلف را نصب کنید.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                    ]))
                return
            elif status_info["status"] == "inactive":
                await app.edit_message_text(chat_id, m_id,
                    "**• ربات دستیار شما نصب نشده است، ابتدا ربات را نصب کرده و در صورت ایجاد مشکل به این بخش مراجعه کنید.**",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="نصب سلف", callback_data="InstallSelf")],
                        [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                    ]))
                return
            else:
                status_message = (
                    f"**درخواست شما با موفقیت انجام شد.**\n\n"
                    f"**نتیجه:** {status_info['message']}\n\n"
                )
                
                if status_info["language"]:
                    status_message += f"**توجه: دستیار شما روی زبان {status_info['language']} تنظیم شده و فقط به دستورات با این زبان پاسخ خواهد داد.**"
                
                await app.edit_message_text(chat_id, m_id, status_message,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                    ]))
        else:
            await app.answer_callback_query(call.id, text="• شما انقضا ندارید •", show_alert=True)
    
    elif data == "ChangeLang":
        if expir > 0:
            can_change, remaining = can_change_language(chat_id)
            
            if not can_change:
                await app.edit_message_text(call.from_user.id, m_id, 
                    f"**• تغییر زبان دستیار شما تا {remaining} دقیقه دیگر امکان پذیر نیست.**")
                return
            
            current_lang = get_current_language(chat_id)
            
            next_lang = "en" if current_lang == "fa" else "fa"
            next_lang_display = "انگلیسی 🇬🇧" if next_lang == "en" else "فارسی 🇮🇷"
            current_lang_display = "فارسی 🇮🇷" if current_lang == "fa" else "انگلیسی 🇬🇧"
            
            await app.edit_message_text(chat_id, m_id,
                f"**• آیا میخواهید زبان دستیار شما از ( {current_lang_display} ) به ( {next_lang_display} ) تنظیم شود؟**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="بله ✔️", callback_data=f"ConfirmLangChange-{next_lang}"),
                     InlineKeyboardButton(text="خیر ✖️", callback_data="Back")]
                ]))
        else:
            await app.answer_callback_query(call.id, text="• شما انقضا ندارید •", show_alert=True)
    
    elif data.startswith("ConfirmLangChange-"):
        target_lang = data.split("-")[1]
        
        success, result = await change_self_language(chat_id, target_lang)
        
        if success:
            new_lang_display = "فارسی 🇮🇷" if target_lang == "fa" else "انگلیسی 🇬🇧"
            
            await app.edit_message_text(chat_id, m_id,
                f"**• زبان دستیار شما روی ( {new_lang_display} ) تنظیم شد.**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                ]))
            
            user_data = get_data(f"SELECT pid FROM user WHERE id = '{chat_id}' LIMIT 1")
            pid = user_data.get("pid") if user_data else None
            
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    await asyncio.sleep(3)
                    
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
                        
                except Exception as e:
                    pass
        else:
            await app.edit_message_text(chat_id, m_id,
                f"**• عملیات کنسل شد، با پشتیبانی در ارتباط باشید.***",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                ]))
    
    elif data == "AdminCreateCode":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id,
                                   "**لطفا تعداد روز انقضای کد را وارد کنید:**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]
                                   ]))
            update_data(f"UPDATE user SET step = 'admin_create_code_days' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "AdminListCodes":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            cleanup_inactive_codes()
            
            codes = get_active_codes()
            
            if codes:
                codes_text = "**• لیست کدهای فعال :\n\n"
                for idx, code in enumerate(codes, 1):
                    codes_text += f"**{idx} - کد : ( `{code['code']}` )**\n"
                    codes_text += f"**• روزهای انقضا : ( {code['days']} روز )**\n"
                    codes_text += f"**• تاریخ ایجاد : ( {code['created_at']} )**\n\n"
                
                await app.edit_message_text(chat_id, m_id, codes_text,
                                       reply_markup=InlineKeyboardMarkup([
                                           [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]
                                       ]))
            else:
                await app.edit_message_text(chat_id, m_id,
                                       "**هیچ کد فعالی وجود ندارد.**",
                                       reply_markup=InlineKeyboardMarkup([
                                           [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]
                                       ]))

    elif data == "AdminDeleteCode":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            codes = get_active_codes()
            
            if codes:
                keyboard_buttons = []
                for code in codes:
                    keyboard_buttons.append([
                        InlineKeyboardButton(text=f"• {code['code']}", callback_data=f"DeleteCode-{code['id']}")
                    ])
                keyboard_buttons.append([InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")])
                
                await app.edit_message_text(chat_id, m_id,
                                       "**لطفا کدی که می خواهید حذف کنید را انتخاب کنید:**",
                                       reply_markup=InlineKeyboardMarkup(keyboard_buttons))
            else:
                await app.answer_callback_query(call.id, text="• کد فعالی وجود ندارد •", show_alert=True)

    elif data.startswith("DeleteCode-"):
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            code_id = data.split("-")[1]
            delete_code(code_id)
            await app.edit_message_text(chat_id, m_id,
                                   "**کد با موفقیت حذف شد.**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="DeleteCode-")]
                                   ]))
    
    elif data == "BuyCode":
        await app.edit_message_text(chat_id, m_id,
                               "**• لطفا کد انقضای خریداری شده خود را ارسال کنید:**",
                               reply_markup=InlineKeyboardMarkup([
                                   [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="Back")]
                               ]))
        update_data(f"UPDATE user SET step = 'use_code' WHERE id = '{call.from_user.id}' LIMIT 1")
        
    elif data == "AdminSettings":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id,
                                   "**مدیر گرامی، به بخش تنظیمات خوش آمدید.\nلطفا گزینه مورد نظر را انتخاب کنید:**",
                                   reply_markup=AdminSettingsKeyboard)
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "EditStartMessage":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            current_message = get_setting("start_message")
            await app.edit_message_text(chat_id, m_id,
                                   f"**متن فعلی پیام استارت:**\n\n{current_message}\n\n**لطفا متن جدید را ارسال کنید:**\n\n**نکته:** برای نمایش نام کاربر میتوانید از `{{user_link}}` استفاده کنید.",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                   ]))
            update_data(f"UPDATE user SET step = 'edit_start_message' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "EditPriceMessage":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            current_message = get_setting("price_message")
            await app.edit_message_text(chat_id, m_id,
                                   f"**متن فعلی پیام نرخ:**\n\n{current_message}\n\n**لطفا متن جدید را ارسال کنید:**\n\n**نکته:** برای نمایش قیمت‌ها میتوانید از متغیرهای زیر استفاده کنید:\n- `{{price_1month}}`\n- `{{price_2month}}`\n- `{{price_3month}}`\n- `{{price_4month}}`\n- `{{price_5month}}`\n- `{{price_6month}}`",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                   ]))
            update_data(f"UPDATE user SET step = 'edit_price_message' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "EditSelfMessage":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            current_message = get_setting("whatself_message")
            await app.edit_message_text(chat_id, m_id,
                                   f"**متن فعلی توضیح سلف:**\n\n{current_message}\n\n**لطفا متن جدید را ارسال کنید:**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                   ]))
            update_data(f"UPDATE user SET step = 'edit_self_message' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "EditPrices":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            f"**لطفا نرخ موردنظر خودتون رو به صورت زیر وارد کنید.\n( به صورت خط به خط ، خط اول نزخ یک ماهه، خط دوم نرخ دو ماهه و به همین صورت تا نرخ 6 ماهه )\n\n100000\n200000\n300000\n400000\n500000\n600000**"
    
            await app.edit_message_text(chat_id, m_id, prices_text,
                               reply_markup=InlineKeyboardMarkup([
                                   [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                               ]))
            update_data(f"UPDATE user SET step = 'edit_all_prices' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "EditCardInfo":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            current_card = get_setting("card_number")
            current_name = get_setting("card_name")
        
            await app.edit_message_text(chat_id, m_id,
                                   f"**اطلاعات فعلی کارت:**\n\n**شماره کارت:** `{current_card}`\n**نام صاحب کارت:** {current_name}\n\n**لطفا گزینه مورد نظر را انتخاب کنید:**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="تغییر شماره کارت", callback_data="EditCardNumber")],
                                       [InlineKeyboardButton(text="تغییر نام صاحب کارت", callback_data="EditCardName")],
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                   ]))

    elif data == "EditCardNumber":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            current_card = get_setting("card_number")
            await app.edit_message_text(chat_id, m_id,
                                   f"**شماره کارت فعلی:** `{current_card}`\n\n**لطفا شماره کارت جدید را وارد کنید:**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="EditCardInfo")]
                                   ]))
            update_data(f"UPDATE user SET step = 'edit_card_number' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "EditCardName":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            current_name = get_setting("card_name")
            await app.edit_message_text(chat_id, m_id,
                                   f"**نام صاحب کارت فعلی:** {current_name}\n\n**لطفا نام جدید را وارد کنید:**",
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="EditCardInfo")]
                                   ]))
            update_data(f"UPDATE user SET step = 'edit_card_name' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "ViewSettings":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            settings = get_all_settings()
            settings_text = "**تنظیمات فعلی ربات:**\n\n"
            for setting in settings:
                key = setting[1]
                value = setting[2][:50] + "..." if len(str(setting[2])) > 50 else setting[2]
                desc = setting[3]
                settings_text += f"**{desc}:**\n`{key}` = `{value}`\n\n"
        
            await app.edit_message_text(chat_id, m_id, settings_text,
                                   reply_markup=InlineKeyboardMarkup([
                                       [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                   ]))
    
    elif data == "InstallSelf":
        if expir > 0:
                user_info = get_data(f"SELECT phone, api_id, api_hash FROM user WHERE id = '{chat_id}' LIMIT 1")
        
                if user_info and user_info["phone"] and user_info["api_id"] and user_info["api_hash"]:
                    
                    api_hash = user_info["api_hash"]
                    if len(api_hash) >= 8:
                        masked_hash = f"{api_hash[:4]}{'*' * (len(api_hash)-8)}{api_hash[-4:]}"
                    else:
                        masked_hash = "****"
                    await app.edit_message_text(chat_id, m_id,
                        f"**📞 Number : `{user_info['phone']}`\n🆔 Api ID : `{user_info['api_id']}`\n🆔 Api Hash : `{masked_hash}`\n\n• آیا اطلاعات را تایید میکنید؟**",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("بله (✅)", callback_data="ConfirmInstall"),
                            InlineKeyboardButton("خیر (❎)", callback_data="ChangeInfo")],
                            [InlineKeyboardButton("(🔙) بازگشت", callback_data="Back")]
                        ]))
                else:
                    await app.edit_message_text(chat_id, m_id,
                        "**برای نصب سلف، لطفا شماره تلفن خود را با دکمه زیر به اشتراک بگذارید:**",
                        reply_markup=ReplyKeyboardMarkup(
                            [[KeyboardButton(text="اشتراک گذاری شماره", request_contact=True)]],
                            resize_keyboard=True
                        ))
                    update_data(f"UPDATE user SET step = 'install_phone' WHERE id = '{chat_id}' LIMIT 1")
        else:
            await app.send_message(chat.id, "**شما انقضا ندارید.**")
    
    elif data == "ConfirmInstall":
        user_info = get_data(f"SELECT phone, api_id, api_hash FROM user WHERE id = '{chat_id}' LIMIT 1")
        if user_info and user_info["phone"] and user_info["api_id"] and user_info["api_hash"]:
            await app.edit_message_text(chat_id, m_id,
                "**• زبان سلف را انتخاب کنید.**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("فارسی 🇮🇷", callback_data=f"SelectLanguage-fa"),
                    InlineKeyboardButton("English 🇬🇧", callback_data=f"SelectLanguage-en")],
                    [InlineKeyboardButton("(🔙) بازگشت", callback_data="Back")]
                ]))
            update_data(f"UPDATE user SET step = 'select_language-{user_info['phone']}-{user_info['api_id']}-{user_info['api_hash']}' WHERE id = '{chat_id}' LIMIT 1")
        else:
            await app.answer_callback_query(call.id, text="• اطلاعات شما ناقص است •", show_alert=True)

    elif data.startswith("SelectLanguage-"):
        target_language = data.split("-")[1]
        user_step = user["step"]
    
        if user_step.startswith("select_language-"):
            parts = user_step.split("-", 1)
            if len(parts) > 1:
                remaining_parts = parts[1]
                update_data(f"UPDATE user SET step = 'install_with_language-{remaining_parts}-{target_language}' WHERE id = '{chat_id}' LIMIT 1")
            
                remaining_parts_parts = remaining_parts.split("-")
                if len(remaining_parts_parts) >= 3:
                    phone = remaining_parts_parts[0]
                    api_id = remaining_parts_parts[1]
                    api_hash = remaining_parts_parts[2]
                
                    await app.edit_message_text(chat_id, m_id, "**• درحال ساخت سلف، لطفا صبور باشید.**")
                
                    await start_self_installation(chat_id, phone, api_id, api_hash, m_id, target_language)

    elif data == "ChangeInfo":
        await app.edit_message_text(chat_id, m_id,
            "**لطفا شماره تلفن خود را با دکمه زیر به اشتراک بگذارید:**",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(text="اشتراک گذاری شماره", request_contact=True)]],
                resize_keyboard=True
            ))
        update_data(f"UPDATE user SET step = 'install_phone' WHERE id = '{chat_id}' LIMIT 1")

    elif data == "StartInstallation":
        user_info = get_data(f"SELECT phone, api_id, api_hash FROM user WHERE id = '{chat_id}' LIMIT 1")
        if user_info and user_info["phone"] and user_info["api_id"] and user_info["api_hash"]:
            await app.edit_message_text(chat_id, m_id, "**• درحال ساخت سلف، لطفا صبور باشید.**")
            await start_self_installation(chat_id, user_info["phone"], user_info["api_id"], user_info["api_hash"])
        else:
            await app.answer_callback_query(call.id, text="• اطلاعات شما ناقص است •", show_alert=True)
    
    elif data == "ExpiryStatus":
        await app.answer_callback_query(call.id, text=f"انقضای شما : ( {expir} روز )", show_alert=True)

    elif data == "AdminPanel":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, "**مدیر گرامی، به پنل ربات سلف ساز تلگرام خوش آمدید.\nاکنون ربات کاملا در اختیار شماست، در صورتی که آشنایی با پنل مدیریت یا کارکرد ربات ندارید، بخش « راهنما » را بخوانید.**", reply_markup=AdminPanelKeyboard)
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
            async with lock:
                if chat_id in temp_Client:
                    del temp_Client[chat_id]
        else:
            await app.answer_callback_query(call.id, text="**شما دسترسی به بخش مدیریت ندارید.**", show_alert=True)
    
    elif data == "AdminStats":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            botinfo = await app.get_me()
            allusers = get_datas("SELECT COUNT(id) FROM user")[0][0]
            allblocks = get_datas("SELECT COUNT(id) FROM block")[0][0]
            pending_cards = len(get_pending_cards())
            
            await app.edit_message_text(chat_id, m_id, f"""
            • تعداد کل کاربران ربات : **[ {allusers} ]**
            • تعداد کاربران بلاک شده :  **[ {allblocks} ]**
            • تعداد کارت های در انتضار تایید : **[ {pending_cards} ]**
            
            • نام ربات : **( {botinfo.first_name} )**
            • آیدی عددی ربات : **( `{botinfo.id}` )**
            • آیدی ربات : **( @{botinfo.username} )**
            """, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
    
    elif data == "AdminBroadcast":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, f"**پیام خود را جهت ارسال همگانی، ارسال کنید.**\n\n• با ارسال پیام در این بخش، پیام شما برای تمامی کاربران ربات **ارسال** میشود.", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_broadcast' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminForward":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, f"**پیام خود را جهت فوروارد همگانی ارسال کنید.**\n\n• با ارسال پیام در این بخش، پیام شما برای تمامی کاربران ربات **فوروارد** میشود.", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_forward' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminBlock":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, "**آیدی عددی کاربر را جهت مسدود از ربات ارسال کنید:**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_block' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminUnblock":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, "**آیدی عددی کاربر را جهت پاک کردن از لیست مسدود ها ارسال کنید:**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_unblock' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminAddExpiry":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, "**• آیدی عددی کاربر را جهت افزایش انقضا ارسال کنید:**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_add_expiry1' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminDeductExpiry":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, "**• آیدی عددی کاربر را جهت کسر انقضا ارسال کنید:**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_deduct_expiry1' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminActivateSelf":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, "**آیدی عددی کاربر را جهت فعالسازی سلف ارسال کنید:**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_activate_self' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminDeactivateSelf":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            await app.edit_message_text(chat_id, m_id, "**آیدی عددی کاربر را جهت غیرفعال سازی سلف ارسال کنید:**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'admin_deactivate_self' WHERE id = '{chat_id}' LIMIT 1")
    
    elif data == "AdminTurnOn":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            bot = get_data("SELECT * FROM bot")
            if bot["status"] != "ON":
                await app.edit_message_text(chat_id, m_id, "**• ربات روشن شد.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
                update_data(f"UPDATE bot SET status = 'ON' LIMIT 1")
            else:
                await app.answer_callback_query(call.id, text="**• ربات روشن بوده است.**", show_alert=True)
    
    elif data == "AdminTurnOff":
        if call.from_user.id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{call.from_user.id}' LIMIT 1") is not None:
            bot = get_data("SELECT * FROM bot")
            if bot["status"] != "OFF":
                await app.edit_message_text(chat_id, m_id, "**• ربات خاموش شد.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
                update_data(f"UPDATE bot SET status = 'OFF' LIMIT 1")
            else:
                await app.answer_callback_query(call.id, text="**• ربات خاموش بوده است.**", show_alert=True)
    
    elif data.startswith("AdminVerifyCard-"):
        params = data.split("-")
        user_id = int(params[1])
        card_number = params[2]
    
        bank_name = detect_bank(card_number)
        card = get_card_by_number(user_id, card_number)
    
        if card:
            update_card_status(card["id"], "verified", bank_name)
    
        user_info = await app.get_users(user_id)
        username = f"@{user_info.username}" if user_info.username else "ندارد"
    
        await app.edit_message_text(call.message.chat.id, call.message.id, f"""**• درخواست احراز هویت از طرف ( {html.escape(user_info.first_name)} - {username} - {user_id} )
• شماره کارت : [ {card_number} ]

به دستور ( {call.from_user.id} ) تایید شد.**""")
    
        await app.send_message(user_id, f"**• درخواست احراز هویت کارت ( `{card_number}` ) تایید شد.\nشما هم اکنون میتوانید از بخش خرید / تمدید اشتراک ، خرید خود را انجام دهید.**")

    elif data.startswith("AdminRejectCard-"):
        params = data.split("-")
        user_id = int(params[1])
        card_number = params[2]
    
        card = get_card_by_number(user_id, card_number)
        if card:
            update_card_status(card["id"], "rejected")
        user_info = await app.get_users(user_id)
        username = f"@{user_info.username}" if user_info.username else "ندارد"
    
        await app.edit_message_text(call.message.chat.id, call.message.id, f"""**• درخواست احراز هویت از طرف ( {html.escape(user_info.first_name)} - {username} - {user_id} )
• شماره کارت : [ {card_number} ]

به دستور ( {call.from_user.id} ) رد شد.**""")
    
        await app.send_message(user_id, f"**• درخواست احراز هویت کارت ( {card_number} ) به دلیل اشتباه بودن، رد شد.\nشما میتوانید مجددا برای احراز هویت با رعایت شرایط، درخواست دهید.**")

    elif data.startswith("AdminIncompleteCard-"):
        params = data.split("-")
        user_id = int(params[1])
        card_number = params[2]
    
        card = get_card_by_number(user_id, card_number)
        if card:
            update_card_status(card["id"], "rejected")
        user_info = await app.get_users(user_id)
        username = f"@{user_info.username}" if user_info.username else "ندارد"
    
        await app.edit_message_text(call.message.chat.id, call.message.id, f"""**• درخواست احراز هویت از طرف ( {html.escape(user_info.first_name)} - {username} - {user_id} )
• شماره کارت : [ {card_number} ]

به دستور ( {call.from_user.id} ) رد شد.**""")
    
        await app.send_message(user_id, f"**• درخواست احراز هویت کارت ( {card_number} ) به دلیل ناقص بودن ، رد شد.\nشما میتوانید مجددا برای احراز هویت با رعایت شرایط، درخواست دهید.**")
    
    elif data.startswith("AdminApprovePayment-"):
        params = data.split("-")
        user_id = int(params[1])
        expir_count = int(params[2])
        cost = params[3]
        transaction_id = params[4]
        
        user_data = get_data(f"SELECT expir FROM user WHERE id = '{user_id}' LIMIT 1")
        old_expir = user_data["expir"] if user_data else 0
        new_expir = old_expir + expir_count
        
        update_data(f"UPDATE user SET expir = '{new_expir}' WHERE id = '{user_id}' LIMIT 1")
        
        if expir_count == 31:
            month_text = "یک ماه"
        elif expir_count == 62:
            month_text = "دو ماه"
        elif expir_count == 93:
            month_text = "سه ماه"
        elif expir_count == 124:
            month_text = "چهار ماه"
        elif expir_count == 155:
            month_text = "پنج ماه"
        elif expir_count == 186:
            month_text = "شش ماه"
        else:
            month_text = f"{expir_count} روز"
        
        await app.edit_message_text(Admin, m_id, f"**پرداخت کاربر [ `{user_id}` ] تایید شد.\n\n• شناسه تراکنش : [ `{transaction_id}` ]\n• انقضای جدید کاربر : [ `{new_expir} روز` ]**")
        
        await app.send_message(user_id, f"**پرداخت شما تایید شد.\n\n• شناسه تراکنش : [ {transaction_id} ]\n• انقضای سلف شما {month_text} اضافه گردید.\n\nانقضای قبلی شما : ( `{old_expir}` ) روز\n\n• انقضای جدید : ( `{new_expir}` ) روز**")
    
    elif data.startswith("AdminRejectPayment-"):
        params = data.split("-")
        user_id = int(params[1])
        transaction_id = params[2]
        
        await app.edit_message_text(Admin, m_id,f"**• پرداخت کاربر [ `{user_id}` ] رد شد.**")
        
        await app.edit_message_text(user_id, f"**پرداخت شما رد گردید.\n\n•شناسه تراکنش : [ `{transaction_id}` ]\n• افزایش انقضای شما به دلیل ارسال فیش واربزی اشتباه رد شده و درخواست شما لغو گردید.\n• در صورتی که غکر میکنید اشتباه شده است، شناسه تراکنش را به پشتیبانی ارسال کرده و با پشتیان ها در ارتباط باشید.**")
    
    elif data.startswith("AdminBlockPayment-"):
        user_id = int(data.split("-")[1])
        
        update_data(f"INSERT INTO block(id) VALUES({user_id})")
        
        await app.edit_message_text(Admin, m_id, f"**• کاربر [ `{user_id}` ] از ربات مسدود شد.**")
        
        await app.send_message(user_id, f"**شما به دلیل نقض قوانین از ربات مسدود شده اید.\n• با پشتیبان ها در ارتباط باشید.**")
    
    elif data.startswith("Reply-"):
        user_id = int(data.split("-")[1])
        user_info = await app.get_users(user_id)
        await app.send_message(
            Admin,
            f"**• پیام خود را جهت پاسخ به کاربر [ {html.escape(user_info.first_name)} ] ارسال کنید:**",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            )
        )
        update_data(f"UPDATE user SET step = 'ureply-{user_id}' WHERE id = '{Admin}' LIMIT 1")

    elif data.startswith("Block-"):
        user_id = int(data.split("-")[1])
        user_info = await app.get_users(user_id)
        block = get_data(f"SELECT * FROM block WHERE id = '{user_id}' LIMIT 1")
        if block is None:
            await app.send_message(user_id, "**شما به دلیل نقض قوانین از ربات مسدود شدید.**")
            await app.send_message(Admin, f"**• کاربر [ {html.escape(user_info.first_name)} ] از ربات مسدود شد.**")
            update_data(f"INSERT INTO block(id) VALUES({user_id})")
        else:
            await app.send_message(Admin, f"**• کاربر [ {html.escape(user_info.first_name)} ] از قبل بلاک بوده است.**")

    elif data == "Back":
        keyboard = get_main_keyboard(call.from_user.id)
        await app.edit_message_text(chat_id, m_id, "**‌ ‌ ‌ ‌ ‌ ‌ ‌     ‌ ‌‌‌  ‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌‌‌‌‌‌ \nبه منوی اصلی بازگشتید.\n\nلطفا اگر سوالی دارید از بخش پشتیبانی ، با پستیبان ها در ارتباط باشید.\n\n‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌ ‌ لطفا انتخاب کنید:\n‌ ‌ ‌‌        ‌‌‌‌‌‌    ‌‌‌‌‌‌ ‌‌‌‌‌**", reply_markup=keyboard)
        update_data(f"UPDATE user SET step = 'none' WHERE id = '{call.from_user.id}' LIMIT 1")
        async with lock:
            if chat_id in temp_Client:
                del temp_Client[chat_id]
    
    elif data == "text":
        await app.answer_callback_query(call.id, text="• دکمه نمایشی است •", show_alert=True)

@app.on_message(filters.contact)
@checker
async def contact_handler(c, m):
    user = get_data(f"SELECT * FROM user WHERE id = '{m.chat.id}' LIMIT 1")
    
    phone_number = str(m.contact.phone_number)
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"
    
    is_valid, error_message = validate_phone_number(phone_number)
    
    if not is_valid:
        await app.send_message(m.chat.id, f"**• تا اطلاع ثانوی، امکان خرید، نصب دستیار با شماره های خارج از ایران غیرمجاز میباشد.**.")
        return
    
    contact_id = m.contact.user_id
    
    if user["step"] == "install_phone":
        if m.contact and m.chat.id == contact_id:
            update_data(f"UPDATE user SET phone = '{phone_number}' WHERE id = '{m.chat.id}' LIMIT 1")
            Create = f'<a href=https://t.me/{api_channel}>کلیک کنید!</a>'
            await app.send_message(m.chat.id, "**شماره شما ثبت شد.**")
            
            await app.send_message(m.chat.id, f"**• لطفا `Api ID` خود را وارد کنید. ( نمونه : 123456 )**\n• آموزش ساخت : ( {Create} )\n\n**• لغو عملیات [ /start ]**")
            
            update_data(f"UPDATE user SET step = 'install_api_id' WHERE id = '{m.chat.id}' LIMIT 1")
        else:
            await app.send_message(m.chat.id, "**• لطفا شماره خود را با دکمه «اشتراک گذاری شماره» ارسال کنید.**")
        return
    
    elif user["step"] == "contact":
        if m.contact and m.chat.id == contact_id:
            await app.send_message(m.chat.id, 
                                 "**• شماره شما با موفقیت ذخیره شد.\nاکنون می‌توانید از بخش خرید استفاده کنید.\n\nربات رو مجددا [ /start ] کنید.**", 
                                 reply_markup=ReplyKeyboardRemove())
            update_data(f"UPDATE user SET phone = '{phone_number}' WHERE id = '{m.chat.id}' LIMIT 1")
        else:
            await app.send_message(m.chat.id, "**• با استفاده از دکمه « اشتراک گذاری شماره » شماره تلفن را ارسال نمایید.**")

@app.on_message(filters.private)
@checker
async def message_handler(c, m):
    global temp_Client
    user = get_data(f"SELECT * FROM user WHERE id = '{m.chat.id}' LIMIT 1")
    username = f"@{m.from_user.username}" if m.from_user.username else "وجود ندارد"
    expir = user["expir"] if user else 0
    chat_id = m.chat.id
    text = m.text
    m_id = m.id

    if user["step"] == "card_photo":
        if m.photo:
            photo_path = await m.download(file_name=f"cards/{chat_id}_{int(time.time())}.jpg")
            update_data(f"UPDATE user SET step = 'card_number-{photo_path}-{m_id}' WHERE id = '{m.chat.id}' LIMIT 1")
            
            await app.send_message(chat_id,
                                 "**• لطفا شماره کارت خود را به صورت اعداد انگلیسی ارسال کنید.\nدر صورتی که منصرف شدید ربات را مجدد [ /start ] کنید.**")
        else:
            await app.send_message(chat_id, "**• فقط ارسال عکس مجاز است.**")

    elif user["step"].startswith("card_number-"):
        if text and text.isdigit() and len(text) == 16:
            parts = user["step"].split("-", 2)
            photo_path = parts[1]
            photo_message_id = parts[2] if len(parts) > 2 else None
        
            card_number = text.strip()
    
            add_card(chat_id, card_number)
    
            if photo_message_id:
                try:
                    forwarded_photo_msg = await app.forward_messages(
                        from_chat_id=chat_id,
                        chat_id=Admin,
                        message_ids=int(photo_message_id)
                    )
                
                    await app.send_message(
                        Admin,
                        f"""**• درخواست احراز هویت از طرف ( {html.escape(m.chat.first_name)} - @{m.from_user.username if m.from_user.username else 'ندارد'} - {m.chat.id} )
شماره کارت : [ {card_number} ]**""",
                        reply_to_message_id=forwarded_photo_msg.id,
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(text="تایید (✅)", callback_data=f"AdminVerifyCard-{chat_id}-{card_number}")
                            ],
                            [
                                InlineKeyboardButton(text="اشتباه (❌)", callback_data=f"AdminRejectCard-{chat_id}-{card_number}"),
                                InlineKeyboardButton(text="کامل نیست (❌)", callback_data=f"AdminIncompleteCard-{chat_id}-{card_number}")
                            ]
                        ])
                    )
                except Exception as e:
                    await app.send_message(
                        Admin,
                        f"""**• درخواست احراز هویت از طرف ({html.escape(m.chat.first_name)} - @{m.from_user.username if m.from_user.username else 'ندارد'} - {m.chat.id})
شماره کارت : [ {card_number} ]**""",
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(text="تایید (✅)", callback_data=f"AdminVerifyCard-{chat_id}-{card_number}"),
                                InlineKeyboardButton(text="اشتباه (❌)", callback_data=f"AdminRejectCard-{chat_id}-{card_number}"),
                                InlineKeyboardButton(text="کامل نیست (❌)", callback_data=f"AdminIncompleteCard-{chat_id}-{card_number}")
                            ]
                        ])
                    )
            else:
                await app.send_message(
                    Admin,
                    f"""**• درخواست احراز هویت از طرف ({html.escape(m.chat.first_name)} - @{m.from_user.username if m.from_user.username else 'ندارد'} - {m.chat.id})
شماره کارت : [ {card_number} ]**""",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(text="تایید (✅)", callback_data=f"AdminVerifyCard-{chat_id}-{card_number}"),
                            InlineKeyboardButton(text="اشتباه (❌)", callback_data=f"AdminRejectCard-{chat_id}-{card_number}"),
                            InlineKeyboardButton(text="کامل نیست (❌)", callback_data=f"AdminIncompleteCard-{chat_id}-{card_number}")
                        ]
                    ])
                )
    
            await app.send_message(chat_id,
                            """**• درخواست احراز هویت شما برای پشتیبانی ارسال شد و در اولین فرصت تایید خواهد شد ، لطفا صبور باشید.

لطفا برای تایید کارت به پشتیبانی پیام ارسال نفرمایید و درخواست احرازهویتتون رو اسپم نکنید ، در صورت مشاهده این کار یک روز با تاخیر تایید میشود.**""")
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{m.chat.id}' LIMIT 1")
        else:
            await app.send_message(chat_id, "**شماره کارت باید 16 رقم باشد.\n• در صورتی که منصرف شدید ربات رو مجددا [ /start ] کنید.**")

    elif user["step"].startswith("payment_receipt-"):
        if m.photo:
            params = user["step"].split("-")
            expir_count = params[1]
            cost = params[2]
            card_id = params[3]
            
            card = get_card_by_id(card_id)
            card_number = card["card_number"] if card else "نامشخص"
            
            mess = await app.forward_messages(from_chat_id=chat_id, chat_id=Admin, message_ids=m_id)
            
            transaction_id = str(int(time.time()))[-11:]
            
            await app.send_message(Admin,
                                 f"""**• درخواست خرید اشتراک از طرف ( {html.escape(m.chat.first_name)} - @{m.from_user.username if m.from_user.username else 'ندارد'} - {m.chat.id} )
اشتراک انتخاب شده : ( `{cost} تومان - {expir_count} روز` )
کارت خرید : ( `{card_number}` )**""",
                                 reply_to_message_id=mess.id,
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton(text="تایید (✅)", callback_data=f"AdminApprovePayment-{chat_id}-{expir_count}-{cost}-{transaction_id}")],
                                      [InlineKeyboardButton(text="مسدود (❌)", callback_data=f"AdminBlockPayment-{chat_id}"),
                                      InlineKeyboardButton(text="رد (❌)", callback_data=f"AdminRejectPayment-{chat_id}-{transaction_id}")]
                                 ]))
            
            await app.send_message(chat_id,
                                 f"""**فیش واریزی شما ارسال شد.
• شناسه تراکنش: [ `{transaction_id}` ]
منتظر تایید فیش توسط مدیر باشید.**""")
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{m.chat.id}' LIMIT 1")
        else:
            await app.send_message(chat_id, "**فقط عکس فیش واریزی را ارسال کنید.**")

    elif user["step"] == "support":
        mess = await app.forward_messages(from_chat_id=chat_id, chat_id=Admin, message_ids=m_id)
        await app.send_message(Admin, f"""**
• پیام جدید از طرف ( {html.escape(m.chat.first_name)} - `{m.chat.id}` - {username} )**\n
""", reply_to_message_id=mess.id, reply_markup=InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("پاسخ (✅)", callback_data=f"Reply-{m.chat.id}"),
                InlineKeyboardButton("مسدود (❌)", callback_data=f"Block-{m.chat.id}")
            ]
        ]
    ))
        await app.send_message(chat_id, "**• پیام شما به پشتیبانی ارسال شد.\nلطفا در بخش پشتیبانی اسپم نکنید و از دستورات استفاده نکنید به پیام شما در اسرع وقت پاسخ داده خواهد شد.**", reply_to_message_id=m_id)
    
    elif user["step"] == "install_phone":
        if m.contact:
            phone_number = str(m.contact.phone_number)
            if not phone_number.startswith("+"):
                phone_number = f"+{phone_number}"
        
            update_data(f"UPDATE user SET phone = '{phone_number}' WHERE id = '{chat_id}'")
            update_data(f"UPDATE user SET step = 'install_api_id' WHERE id = '{chat_id}'")
        
            Create = f'<a href=https://t.me/{api_channel}>کلیک کنید!</a>'
            await app.send_message(m.chat.id, "**شماره شما ثبت شد.")
            
            await app.send_message(m.chat.id, f"**• لطفا `Api ID` خود را وارد کنید. ( نمونه : 123456 )**\n• آموزش ساخت : ( {Create} )\n\n**• لغو عملیات [ /start ]**")
        else:
            await app.send_message(chat_id, "**لطفا با استفاده از دکمه، شماره تلفن را به اشتراک بگذارید.**")

    elif user["step"] == "install_api_id":
        if text and text.isdigit():
            update_data(f"UPDATE user SET api_id = '{text}' WHERE id = '{chat_id}'")
            update_data(f"UPDATE user SET step = 'install_api_hash' WHERE id = '{chat_id}'")
            await app.send_message(m.chat.id, f"**• لطفا `Api Hash` خود را وارد کنید.\n( مثال : abcdefg0123456abcdefg123456789c )\n\n• لغو عملیات [ /start ]**")
        else:
            await app.send_message(chat_id, "**• لطفا یک Api ID معتبر وارد کنید.**")

    elif user["step"] == "install_api_hash":
        if text and len(text) == 32:
            update_data(f"UPDATE user SET api_hash = '{text}' WHERE id = '{chat_id}'")
        
            user_info = get_data(f"SELECT phone, api_id, api_hash FROM user WHERE id = '{chat_id}' LIMIT 1")
            
            api_hash = user_info["api_hash"]
            if len(api_hash) >= 8:
                masked_hash = f"{api_hash[:4]}{'*' * (len(api_hash)-8)}{api_hash[-4:]}"
            else:
                masked_hash = "****"
            
            await app.send_message(chat_id,
                f"**📞 Number : `{user_info['phone']}`\n🆔 Api ID : `{user_info['api_id']}`\n🆔 Api Hash : `{masked_hash}`\n\n• آیا اطلاعات را تایید میکنید؟**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("بله (✅)", callback_data="ConfirmInstall"),
                    InlineKeyboardButton("خیر (❎)", callback_data="ChangeInfo")],
                    [InlineKeyboardButton("(🔙) بازگشت", callback_data="Back")]
            ]))
            
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}'")
        else:
            await app.send_message(chat_id, "**لطفا یک Api Hash معتبر وارد کنید.**")

    elif user["step"].startswith("install_with_language-"):
        parts = user["step"].split("-")
        if len(parts) >= 5:
            phone = parts[1]
            api_id = parts[2]
            api_hash = parts[3]
            language = parts[4]
        
            if text:
                if "." in text:
                    code = "".join(text.split("."))
                else:
                    code = text
        
                if code.isdigit() and len(code) == 5:
                    await verify_code_and_login(chat_id, phone, api_id, api_hash, code, language)
                else:
                    await app.send_message(chat_id, "**• کد وارد شده نامعتبر است، مجدد کد را وارد کنید.**")
            else:
                await app.send_message(chat_id, "**لطفا کد تأیید را ارسال کنید.**")

    elif user["step"].startswith("install_code-"):
        parts = user["step"].split("-")
        phone = parts[1]
        api_id = parts[2]
        api_hash = parts[3]
        language = parts[4] if len(parts) > 4 else "fa"

        if text:
            if "." in text:
                code = "".join(text.split("."))
            else:
                code = text
    
            if code.isdigit() and len(code) == 5:
                await verify_code_and_login(chat_id, phone, api_id, api_hash, code, language)
        
        else:
            await app.send_message(chat_id, "**لطفا کد تأیید را ارسال کنید.**")

    elif user["step"].startswith("install_2fa-"):
        parts = user["step"].split("-")
        phone = parts[1]
        api_id = parts[2]
        api_hash = parts[3]
        language = parts[4] if len(parts) > 4 else "fa"

        if text:
            await verify_2fa_password(chat_id, phone, api_id, api_hash, text, language)
        else:
            await app.send_message(chat_id, "**• لطفا رمز دومرحله ای اکانت را بدون هیچ کلمه یا کاراکتر اضافه ای ارسال کنید :**")
    
    elif user["step"] == "admin_create_code_days":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                days = int(text.strip())
                code = create_code(days)
                await app.send_message(chat_id,
                                 f"**• کد انقضا با موفقیت ایجاد شد.**\n\n"
                                 f"**• کد : ( `{code}` )**\n"
                                 f"**• تعداد روز : ( {days} روز )**\n\n"
                                 f"**• تاریخ ثبت : ( `{time.strftime('%Y-%m-%d %H:%M:%S')}` )",
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]
                                 ]))
                update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
            else:
                await app.send_message(chat_id, "**لطفا یک عدد معتبر وارد کنید.**")

    elif user["step"] == "use_code":
        code_value = text.strip().upper()
        code_data = get_code_by_value(code_value)
        
        if code_data:
            user_data = get_data(f"SELECT expir FROM user WHERE id = '{chat_id}' LIMIT 1")
            old_expir = user_data["expir"] if user_data else 0
            new_expir = old_expir + code_data["days"]
            
            update_data(f"UPDATE user SET expir = '{new_expir}' WHERE id = '{chat_id}' LIMIT 1")
            
            use_code(code_value, chat_id)
            
            user_info = await app.get_users(chat_id)
            username = f"@{user_info.username}" if user_info.username else "ندارد"
            
            days = code_data["days"]
            if days == 31:
                month_text = "یک ماه"
            elif days == 62:
                month_text = "دو ماه"
            elif days == 93:
                month_text = "سه ماه"
            elif days == 124:
                month_text = "چهار ماه"
            elif days == 155:
                month_text = "پنج ماه"
            elif days == 186:
                month_text = "شش ماه"
            else:
                month_text = f"{days} روز"
            
            message_to_user = f"**• افزایش انقضا با موفقیت انجام شد.**\n\n"
            message_to_user += f"**• کد شارژ استفاده شده : ( `{code_value}` )**\n"
            message_to_user += f"**• انقضای سلف شما {month_text} اضافه گردید.**\n\n"
            message_to_user += f"**• انقضای قبلی شما : ( `{old_expir}` روز )**\n\n"
            message_to_user += f"**• انقضای جدید : ( `{new_expir}` روز )**"
            
            await app.send_message(chat_id, message_to_user)
            
            message_to_admin = f"**کاربر ( {html.escape(user_info.first_name)} - {username} - {chat_id} ) با استفاده از کد `{code_value}` مقدار {month_text} انقضا خریداری کرد و این کد از لیست کدها حذف شد.**"
            await app.send_message(Admin, message_to_admin)
            
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
        else:
            await app.send_message(chat_id, "**کد ارسالی صحیح نیست.**")
            
    elif user["step"] == "edit_start_message":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            update_setting("start_message", text)
            await app.send_message(chat_id, "**✅ متن پیام استارت با موفقیت به‌روزرسانی شد.**",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                             ]))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")

    elif user["step"] == "edit_price_message":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            update_setting("price_message", text)
            await app.send_message(chat_id, "**✅ متن پیام نرخ با موفقیت به‌روزرسانی شد.**",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                             ]))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")

    elif user["step"] == "edit_self_message":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            update_setting("whatself_message", text)
            await app.send_message(chat_id, "**✅ متن توضیح سلف با موفقیت به‌روزرسانی شد.**",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                             ]))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")

    elif user["step"] == "edit_all_prices":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            lines = text.strip().split('\n')
        
            if len(lines) != 6:
                await app.send_message(chat_id, "**خطا: باید دقیقا 6 قیمت (هر قیمت در یک خط) وارد کنید.**\n\n**فرمت صحیح:**\n```\nقیمت 1 ماهه\nقیمت 2 ماهه\nقیمت 3 ماهه\nقیمت 4 ماهه\nقیمت 5 ماهه\nقیمت 6 ماهه\n```",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                ]))
                return
        
            price_keys = ['1month', '2month', '3month', '4month', '5month', '6month']
            price_names = {
                '1month': '1 ماهه',
                '2month': '2 ماهه', 
                '3month': '3 ماهه',
                '4month': '4 ماهه',
                '5month': '5 ماهه',
                '6month': '6 ماهه'
            }
        
            valid_prices = []
            errors = []
        
            for i, line in enumerate(lines):
                price_text = line.strip()
                if not price_text.isdigit():
                    errors.append(f"قیمت {price_names[price_keys[i]]} باید عدد باشد: {price_text}")
                else:
                    valid_prices.append((price_keys[i], price_text))
        
            if errors:
                error_text = "**خطا در ورود قیمت‌ها:**\n\n"
                for error in errors:
                    error_text += f"• {error}\n"
                error_text += "\n**لطفا مجددا تلاش کنید.**"
            
                await app.send_message(chat_id, error_text,
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                ]))
                update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
                return
        
            success_text = "**✅ قیمت‌ها با موفقیت به‌روزرسانی شد:**\n\n"
            for key, price in valid_prices:
                update_setting(f"price_{key}", price)
                success_text += f"**{price_names[key]}:** {price} تومان\n"
        
            success_text += "\n**تغییرات ذخیره شدند.**"
        
            await app.send_message(chat_id, success_text,
                            reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                            ]))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")

    elif user["step"] == "edit_card_number":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.replace(" ", "").isdigit() and len(text.replace(" ", "")) >= 16:
                update_setting("card_number", text.replace(" ", ""))
                await app.send_message(chat_id, f"**✅ شماره کارت با موفقیت به `{text}` به‌روزرسانی شد.**",
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                                 ]))
                update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
            else:
                await app.send_message(chat_id, "**شماره کارت نامعتبر است. لطفا یک شماره کارت معتبر وارد کنید.**")

    elif user["step"] == "edit_card_name":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            update_setting("card_name", text)
            await app.send_message(chat_id, f"**✅ نام صاحب کارت با موفقیت به `{text}` به‌روزرسانی شد.**",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminSettings")]
                             ]))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
    
    elif user["step"] == "admin_broadcast":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            mess = await app.send_message(chat_id, "**• ارسال پیام شما درحال انجام است، لطفا صبور باشید.**")
            users = get_datas(f"SELECT id FROM user")
            for user in users:
                await app.copy_message(from_chat_id=chat_id, chat_id=user[0], message_id=m_id)
                await asyncio.sleep(0.1)
            await app.edit_message_text(chat_id, mess.id, "**• پیام شما به تمامی کاربران ارسال شد.**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
    
    elif user["step"] == "admin_forward":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            mess = await app.send_message(chat_id, "**• فوروارد پیام شما درحال انجام است، لطفا صبور باشید.**")
            users = get_datas(f"SELECT id FROM user")
            for user in users:
                await app.forward_messages(from_chat_id=chat_id, chat_id=user[0], message_ids=m_id)
                await asyncio.sleep(0.1)
            await app.edit_message_text(chat_id, mess.id, "**• پیام شما به تمامی کاربران فوروارد شد.**", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
            ))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
    
    elif user["step"] == "admin_block":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(text.strip())
                if get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1") is not None:
                    block = get_data(f"SELECT * FROM block WHERE id = '{user_id}' LIMIT 1")
                    if block is None:
                        await app.send_message(user_id, f"**شما به دلیل نقض قوانین از ربات مسدود شدید.\n• با پشتیان ها در ارتباط باشید.**")
                        await app.send_message(chat_id, f"**کاربر [ `{user_id}` ] از ربات مسدود شد.**", reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                        ))
                        update_data(f"INSERT INTO block(id) VALUES({user_id})")
                    else:
                        await app.send_message(chat_id, f"**کاربر [ `{user_id}` ] از ربات مسدود شد.**", reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                        ))
                else:
                    await app.send_message(chat_id, "**کاربر پیدا نشد.\n• ابتدا آیدی کاربر را بررسی کرده و از ربات بخواهید ربات را [ /start ] کند.**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
    
    elif user["step"] == "admin_unblock":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(text.strip())
                if get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1") is not None:
                    block = get_data(f"SELECT * FROM block WHERE id = '{user_id}' LIMIT 1")
                    if block is not None:
                        await app.send_message(user_id, f"**شما توسط مدیر از لیست سیاه ربات خارج شدید.\n• اکنون میتوانید از ربات استفاده کنید.**")
                        await app.send_message(chat_id, f"**کاربر [ `{user_id}` ] از لیست سیاه خارج شد.**", reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                        ))
                        update_data(f"DELETE FROM block WHERE id = '{user_id}' LIMIT 1")
                    else:
                        await app.send_message(chat_id, f"**کاربر [ `{user_id}` ] در لیست سیاه وجود ندارد.**", reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                        ))
                else:
                    await app.send_message(chat_id, "**کاربر پیدا نشد.\n•ابتدا آیدی ربات را بررسی کرده و از کاربر بخواهید ربات را [ /start ] کند.**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
    
    elif user["step"] == "admin_add_expiry1":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(text.strip())
                if get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1") is not None:
                    await app.send_message(chat_id, "**• آیدی عددی کاربر را جهت افزایش انقضا ارسال کنید.**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
                    update_data(f"UPDATE user SET step = 'admin_add_expiry2-{user_id}' WHERE id = '{chat_id}' LIMIT 1")
                else:
                    await app.send_message(chat_id, f"**کاربر پیدا نشد.\n• ابتدا آیدی کاربر را بررسی کرده و از کاربر بخواهید ربات را [ /start ] کند.**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
    
    elif user["step"].startswith("admin_add_expiry2"):
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(user["step"].split("-")[1])
                count = int(text.strip())
                user_expir = get_data(f"SELECT expir FROM user WHERE id = '{user_id}' LIMIT 1")
                user_upexpir = int(user_expir["expir"]) + int(count)
                update_data(f"UPDATE user SET expir = '{user_upexpir}' WHERE id = '{user_id}' LIMIT 1")
                
                await app.send_message(user_id, f"**افزایش انقضا برای شما انجام شد.\n• ( `{count}` روز ) به انقضای شما اضافه گردید.\n\n• انقضای جدید شما : ( {user_upexpir} روز )\n")
                
                await app.send_message(chat_id, f"**افزایش انقضا برای کاربر [ `{user_id}` ] انجام شد.\n\n• انقضای اضافه شده: ( `{count}` روز )\n• انقضای جدید کاربر : ( `{user_upexpir}` روز )**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
                update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
    
    elif user["step"] == "admin_deduct_expiry1":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(text.strip())
                if get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1") is not None:
                    await app.send_message(chat_id, "**زمان انقضای موردنظر را برای کاهش ارسال کنید:**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
                    update_data(f"UPDATE user SET step = 'admin_deduct_expiry2-{user_id}' WHERE id = '{chat_id}' LIMIT 1")
                else:
                    await app.send_message(chat_id, f"**کاربر پیدا نشد.\n• ابتدا آیدی کاربر را بررسی کرده و از کاربر بخواهید ربات را [ /start ] کند.**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
    
    elif user["step"].startswith("admin_deduct_expiry2"):
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(user["step"].split("-")[1])
                count = int(text.strip())
                user_expir = get_data(f"SELECT expir FROM user WHERE id = '{user_id}' LIMIT 1")
                user_upexpir = int(user_expir["expir"]) - int(count)
                update_data(f"UPDATE user SET expir = '{user_upexpir}' WHERE id = '{user_id}' LIMIT 1")
                
                await app.send_message(user_id, f"**کسر انقضا برای شما انجام شد.\n\nانقضای جدید شما : ( `{user_upexpir}` روز )\n\n• انقضای کسر شده ؛ ( `{count}` روز )**")
                
                await app.send_message(chat_id, f"**کسر انقضا برای کاربر [ `{user_id}` ] انجام شد.\n\n• انقضای کسر شده: ( `{count}` روز )\n• انقضای جدید کاربر : ( `{user_upexpir}` روز )**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
                update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
    
    elif user["step"] == "admin_activate_self":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(text.strip())
                if get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1") is not None:
                    if os.path.isfile(f"sessions/{user_id}.session-journal"):
                        user_data = get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1")
                        if user_data["self"] != "active":
                            mess = await app.send_message(chat_id, f"**• اشتراک سلف برای کاربر [ `{user_id}` ] درحال فعالسازی است، لطفا صبور باشید.**")
                            process = subprocess.Popen(["python3", "self.py", str(user_id), str(API_ID), API_HASH, Helper_ID], cwd=f"selfs/self-{user_id}")
                            await asyncio.sleep(10)
                            if process.poll() is None:
                                await app.edit_message_text(chat_id, mess.id, f"**• ربات سلف با موفقیت برای کاربر [ `{user_id}` ] فعال شد.**", reply_markup=InlineKeyboardMarkup(
                                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                                ))
                                update_data(f"UPDATE user SET self = 'active' WHERE id = '{user_id}' LIMIT 1")
                                update_data(f"UPDATE user SET pid = '{process.pid}' WHERE id = '{user_id}' LIMIT 1")
                                add_admin(user_id)
                                await setscheduler(user_id)
                                await app.send_message(user_id, f"**• اشتراک سلف توسط مدیریت برای شما فعال شد.\nاکنون مجاز به استفاده از ربات دستیار میباشید.**")
                            else:
                                await app.edit_message_text(chat_id, mess.id, f"**فعالسازی سلف برای کاربر [ `{user_id}` ] با خطا مواجه شد.**", reply_markup=InlineKeyboardMarkup(
                                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                                ))
                        else:
                            await app.send_message(chat_id, f"**اشتراک سلف برای کاربر [ `{user_id}` ] غیرفعال بوده است.**", reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                            ))
                    else:
                        await app.send_message(chat_id, f"**کاربر [ `{user_id}` ] اشتراک فعالی ندارد.**", reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                        ))
                else:
                    await app.send_message(chat_id, "**کاربر یافت نشد، ابتدا از کاربر بخواهید ربات را [ /start ] کند.**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
    
    elif user["step"] == "admin_deactivate_self":
        if chat_id == Admin or helper_getdata(f"SELECT * FROM adminlist WHERE id = '{chat_id}' LIMIT 1") is not None:
            if text.isdigit():
                user_id = int(text.strip())
                if get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1") is not None:
                    if os.path.isfile(f"sessions/{user_id}.session-journal"):
                        user_data = get_data(f"SELECT * FROM user WHERE id = '{user_id}' LIMIT 1")
                        if user_data["self"] != "inactive":
                            mess = await app.send_message(chat_id, "**• درحال پردازش، لطفا صبور باشید.**")
                            try:
                                os.kill(user_data["pid"], signal.SIGKILL)
                            except:
                                pass
                            await app.edit_message_text(chat_id, mess.id, f"**• ربات سلف برای کاربر [ `{user_id}` ] غیرفعال شد.**", reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                            ))
                            update_data(f"UPDATE user SET self = 'inactive' WHERE id = '{user_id}' LIMIT 1")
                            if user_id != Admin:
                                delete_admin(user_id)
                            job = scheduler.get_job(str(user_id))
                            if job:
                                scheduler.remove_job(str(user_id))
                            await app.send_message(user_id, f"**کاربر [ `{user_id}` ] سلف شما به دلایلی غیرفعال شد، لطفا با پشتیبان ها در ارتباط باشید.**")
                        else:
                            await app.send_message(chat_id, f"**ربات سلف از قبل برای کاربر [ `{user_id}` ] غیرفعال بوده است.**", reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                            ))
                    else:
                        await app.send_message(chat_id, f"**کاربر [ `{user_id}` ] انقضای فعالی ندارد.**", reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                        ))
                else:
                    await app.send_message(chat_id, "**کاربر یافت نشد، ابتدا از کاربر بخواهید ربات را [ /start ] کند.**", reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                    ))
            else:
                await app.send_message(chat_id, "**فقط ارسال عدد مجاز است.**", reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
                ))
            update_data(f"UPDATE user SET step = 'none' WHERE id = '{chat_id}' LIMIT 1")
            
    elif user["step"].startswith("ureply-"):
        user_id = int(user["step"].split("-")[1])
        mess = await app.copy_message(from_chat_id=Admin, chat_id=user_id, message_id=m_id)
        await app.send_message(user_id, "**• کاربر گرامی، پاسخ شما از پشتیبانی دریافت شد.**", reply_to_message_id=mess.id)
        await app.send_message(Admin, "**• پیام شما برای کاربر ارسال شد.**", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="(🔙) بازگشت", callback_data="AdminPanel")]]
        ))
        update_data(f"UPDATE user SET step = 'none' WHERE id = '{Admin}' LIMIT 1")

# ==================== Inline Query Handler ==================== #
@app.on_inline_query()
async def inline_code_handler(client, inline_query):
    """Handle inline queries for code sharing"""
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id
    
    if not query or not query.isdigit() or len(query) < 5:
        return
    
    user = await cache_manager.get_user(user_id)
    if not user or not user['step'].startswith('install_code-'):
        return
    
    code = query[:5]
    
    # Show inline result
    results = [
        InlineQueryResultArticle(
            title="دریافت کد",
            description=f"کد: {code}",
            id="1",
            input_message_content=InputTextMessageContent(
                message_text=f"**کد تنظیم شد: {code}**"
            )
        )
    ]
    
    await inline_query.answer(
        results=results,
        cache_time=0,
        is_personal=True
    )
    
    # Process the code after a short delay
    await asyncio.sleep(0.5)
    
    step_parts = user['step'].split('-')
    if len(step_parts) >= 4:
        phone = step_parts[1]
        api_id = step_parts[2]
        api_hash = step_parts[3]
        
        await verify_code_and_login(user_id, phone, api_id, api_hash, code)

async def main():
    """Main async function"""
    print(f"{Fore.YELLOW}🚀 Ultra Self Bot v2.0.0 - Optimized Version")
    print(f"{Fore.CYAN}📊 Initializing...")
    
    try:
        # Initialize directories
        await initialize_directories()
        
        # Initialize database
        await initialize_database()
        
        # Start scheduler
        scheduler.start()
        print(f"{Fore.GREEN}✅ Scheduler started")
        
        # Start bot
        await app.start()
        
        bot_info = await app.get_me()
        print(f"{Fore.GREEN}✅ Bot started: @{bot_info.username}")
        print(f"{Fore.CYAN}👤 Admin ID: {Config.ADMIN}")
        print(f"{Fore.CYAN}⚡ Workers: {Config.MAX_WORKERS}")
        print(f"{Fore.CYAN}💾 Cache size: {Config.CACHE_SIZE}")
        print(f"{Fore.MAGENTA}🎯 Bot is running... Press Ctrl+C to stop")
        
        # Keep bot running
        await idle()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⚠️  Shutting down...")
    except Exception as e:
        print(f"{Fore.RED}❌ Fatal error: {e}")
    finally:
        # Cleanup
        print(f"{Fore.YELLOW}🧹 Cleaning up...")
        
        # Stop scheduler
        if scheduler.running:
            scheduler.shutdown()
        
        # Close database pools
        db_pool.close_all()
        
        # Stop bot
        if app.is_connected:
            await app.stop()
        
        print(f"{Fore.GREEN}✅ Cleanup completed")
        print(f"{Fore.CYAN}👋 Goodbye!")

if __name__ == "__main__":
    # Set event loop policy for better performance
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass