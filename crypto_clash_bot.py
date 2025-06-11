import asyncio
import json
import logging
import os
import random
import signal
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure comprehensive logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CryptoClashBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")
        
        # In-memory storage (for production, use Redis/DB)
        self.player_data = {}  # user_id: {streak, last_play, shard_tokens, whale_powerups, og_status}
        self.group_data = {}   # chat_id: {leaderboard, og_count, total_players}
        self.active_predictions = {}  # prediction_id: {user_id, chat_id, crypto, direction, start_price, timestamp, locked}
        self.group_challenges = {}  # challenge_id: {group1, group2, start_time, duration}
        self.daily_challenges = {}  # user_id: {challenge_type, progress, target, reward, completed}
        
        # Price caching for free API (avoid rate limits)
        self.price_cache = {}  # symbol: {price, timestamp}
        self.cache_duration = 30  # Cache prices for 30 seconds
        self.last_api_call = 0  # Track last API call time
        self.min_api_interval = 2  # Minimum 2 seconds between API calls for free tier
        
        # Crypto symbols for predictions
        self.crypto_symbols = ['bitcoin', 'ethereum', 'binancecoin', 'cardano', 'solana']
        self.crypto_display = {
            'bitcoin': 'BTC', 'ethereum': 'ETH', 'binancecoin': 'BNB', 
            'cardano': 'ADA', 'solana': 'SOL'
        }
        
        # Level system configuration
        self.level_requirements = {
            1: 0, 2: 100, 3: 250, 4: 500, 5: 1000, 6: 2000, 7: 4000, 8: 8000, 9: 15000, 10: 30000
        }
        
        # Achievement system
        self.achievements = {
            'first_win': {'name': '🎯 First Blood', 'desc': 'Win your first prediction', 'reward': 500},
            'streak_5': {'name': '🔥 Hot Streak', 'desc': 'Get 5 wins in a row', 'reward': 1000},
            'streak_10': {'name': '⚡ Lightning Rod', 'desc': 'Get 10 wins in a row', 'reward': 2500},
            'whale_user': {'name': '🐋 Whale Rider', 'desc': 'Use whale mode 10 times', 'reward': 1500},
            'high_roller': {'name': '💎 Diamond Hands', 'desc': 'Earn 10,000 shard tokens', 'reward': 3000},
            'prophet': {'name': '🔮 Oracle', 'desc': 'Win 100 predictions', 'reward': 5000},
            'daily_warrior': {'name': '⚔️ Daily Warrior', 'desc': 'Complete 7 daily challenges', 'reward': 2000}
        }
        
        # Daily challenge types
        self.challenge_types = [
            {'type': 'win_streak', 'desc': 'Get 3 wins in a row', 'target': 3, 'reward': 300},
            {'type': 'predictions', 'desc': 'Make 5 predictions today', 'target': 5, 'reward': 200},
            {'type': 'whale_mode', 'desc': 'Use whale mode 2 times', 'target': 2, 'reward': 400},
            {'type': 'perfect_day', 'desc': 'Win 3 predictions without losing', 'target': 3, 'reward': 500}
        ]
        
        # Power-up shop items
        self.shop_items = {
            'whale_powerup': {'name': '🐋 Whale Mode', 'price': 500, 'desc': '3x reward multiplier'},
            'streak_shield': {'name': '🛡️ Streak Shield', 'price': 1000, 'desc': 'Protect your streak once'},
            'double_xp': {'name': '⭐ Double XP', 'price': 300, 'desc': 'Double XP for next 5 predictions'},
            'lucky_charm': {'name': '🍀 Lucky Charm', 'price': 800, 'desc': 'Reduce required move to 0.5%'}
        }
        
        # Crypto slang responses with more variety
        self.win_responses = [
            "🚀 WAGMI! You just went to the moon!",
            "💎 Diamond hands paid off! Shard tokens incoming!",
            "🦍 Ape strong! Your streak is pumping!",
            "⚡ Lightning prediction! The market can't stop you!",
            "🔥 Absolutely based! You're built different!",
            "🎯 Sniper shot! You read the charts perfectly!",
            "👑 Royalty move! You're the alpha trader!",
            "🌙 To the moon! Your prediction was godlike!"
        ]
        
        self.lose_responses = [
            "😵 REKT! The market humbled you this time",
            "📉 Oof, that's a rug pull on your streak",
            "🤡 Paper hands move right there, anon",
            "💸 The market gods demand sacrifice",
            "⛔ Not your keys, not your gains... wait, wrong saying",
            "🔥 Got burned by the market makers!",
            "😭 Even the whales make mistakes sometimes",
            "💀 The bears got you this round!"
        ]
        
        self.level_up_messages = [
            "🎉 LEVEL UP! You're ascending to crypto godhood!",
            "⚡ POWER SURGE! Your trading skills are evolving!",
            "🚀 RANK UP! The moon is getting closer!",
            "👑 ELITE STATUS! You're now among the chosen ones!",
            "💎 DIAMOND TIER! Your hands are getting harder!"
        ]
        
        self.fud_events = [
            "📰 BREAKING: Elon tweets about your prediction!",
            "🏛️ Government FUD incoming! Difficulty +10%",
            "🐋 Whale movement detected! Market volatility high!",
            "📊 Technical analysis says you're wrong (probably)",
            "🌙 Lunar eclipse affecting crypto vibes!"
        ]

    def get_player_data(self, user_id: int) -> Dict:
        """Get or create player data"""
        if user_id not in self.player_data:
            self.player_data[user_id] = {
                'streak': 0,
                'best_streak': 0,
                'last_play': 0,
                'shard_tokens': 1000,  # Starting tokens
                'whale_powerups': 1,   # Starting power-up
                'og_status': False,
                'total_predictions': 0,
                'wins': 0,
                'referrals': 0,
                'level': 1,
                'xp': 0,
                'achievements': [],
                'daily_challenges_completed': 0,
                'streak_shields': 0,
                'double_xp_remaining': 0,
                'lucky_charms': 0,
                'whale_uses': 0,
                'perfect_streak': 0,  # For daily challenges
                'last_challenge_reset': 0
            }
        return self.player_data[user_id]

    def get_group_data(self, chat_id: int) -> Dict:
        """Get or create group data"""
        if chat_id not in self.group_data:
            self.group_data[chat_id] = {
                'leaderboard': {},  # user_id: best_streak
                'og_count': 0,
                'total_players': 0,
                'group_score': 0
            }
        return self.group_data[chat_id]

    async def get_crypto_price(self, symbol: str, retries: int = 2) -> Optional[float]:
        """Fetch current crypto price from CoinGecko FREE API with caching and rate limiting"""
        # Check cache first
        current_time = time.time()
        if symbol in self.price_cache:
            cached_data = self.price_cache[symbol]
            if current_time - cached_data['timestamp'] < self.cache_duration:
                logger.info(f"Using cached price for {symbol}: ${cached_data['price']}")
                return cached_data['price']
        
        # Check API rate limiting for free tier
        time_since_last_call = current_time - self.last_api_call
        if time_since_last_call < self.min_api_interval:
            wait_time = self.min_api_interval - time_since_last_call
            logger.info(f"Rate limiting: waiting {wait_time:.1f}s before API call")
            await asyncio.sleep(wait_time)
        
        # Try to get API key (but we'll use free tier optimizations)
        api_key = os.getenv('COINGECKO_API_KEY')
        
        for attempt in range(retries):
            try:
                logger.info(f"Fetching price for {symbol}, attempt {attempt + 1}")
                
                # Always use free API endpoint but with optimizations
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
                headers = {
                    'User-Agent': 'CryptoClash-Bot/1.0',
                    'Accept': 'application/json'
                }
                
                # Add pro header if available
                if api_key:
                    headers['x-cg-pro-api-key'] = api_key
                    logger.info(f"Using Pro API key for {symbol}")
                else:
                    logger.info(f"Using Free API for {symbol}")
                
                self.last_api_call = time.time()
                response = requests.get(url, headers=headers, timeout=15)
                
                # Handle rate limiting specifically
                if response.status_code == 429:
                    logger.warning(f"Rate limited! Status: 429. Waiting before retry...")
                    retry_after = int(response.headers.get('Retry-After', 60))
                    wait_time = min(retry_after, 60)  # Max 60s wait
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                if symbol not in data:
                    logger.error(f"Symbol {symbol} not found in API response")
                    continue
                    
                price = data[symbol]['usd']
                
                # Cache the price
                self.price_cache[symbol] = {
                    'price': price,
                    'timestamp': time.time()
                }
                
                logger.info(f"Successfully fetched {symbol} price: ${price} (API key: {bool(api_key)})")
                return price
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {symbol} (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(3 + attempt * 2)  # Progressive backoff
                continue
            except Exception as e:
                logger.error(f"Unexpected error fetching price for {symbol} (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                continue
        
        # If all retries failed, try to use cached data even if expired
        if symbol in self.price_cache:
            cached_data = self.price_cache[symbol]
            age_minutes = (time.time() - cached_data['timestamp']) / 60
            logger.warning(f"Using expired cache for {symbol} (age: {age_minutes:.1f}min)")
            return cached_data['price']
        
        logger.error(f"Failed to fetch price for {symbol} after {retries} attempts")
        return None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - welcome new players with enhanced gamification"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "anon"
        
        logger.info(f"🎯 START COMMAND: User {user_id} ({username}) started the bot in chat {chat_id}")
        
        player_data = self.get_player_data(user_id)
        group_data = self.get_group_data(chat_id)
        
        # Generate daily challenge
        self.generate_daily_challenge(user_id)
        
        # Check for OG status (first 10 players in group)
        if not player_data['og_status'] and group_data['og_count'] < 10:
            player_data['og_status'] = True
            group_data['og_count'] += 1
            og_msg = "👑 <b>OG STATUS UNLOCKED!</b> You're among the first 10 legends!"
            logger.info(f"User {user_id} got OG status in chat {chat_id}")
        else:
            og_msg = ""
        
        group_data['total_players'] = len(set(list(group_data['leaderboard'].keys()) + [user_id]))
        
        # Calculate level progression
        current_level = player_data['level']
        next_level_xp = self.get_xp_for_next_level(current_level)
        xp_progress = player_data['xp']
        
        if next_level_xp > 0:
            current_level_xp = self.level_requirements[current_level]
            xp_for_next = next_level_xp - xp_progress
            progress_bar = "█" * int((xp_progress - current_level_xp) / (next_level_xp - current_level_xp) * 10)
            progress_bar += "░" * (10 - len(progress_bar))
            level_display = f"Level {current_level} ⚡ [{progress_bar}] ({xp_for_next} XP to Lv.{current_level + 1})"
        else:
            level_display = f"Level {current_level} ⚡ [██████████] (MAX LEVEL!)"
        
        # Daily challenge info
        daily_challenge = ""
        if user_id in self.daily_challenges:
            challenge = self.daily_challenges[user_id]
            if not challenge['completed']:
                progress = f"{challenge['progress']}/{challenge['target']}"
                daily_challenge = f"🎯 <b>Daily Quest:</b> {challenge['desc']} ({progress}) - {challenge['reward']} tokens"
            else:
                daily_challenge = "✅ <b>Daily Quest:</b> Completed! New challenge tomorrow!"
        
        # Recent achievements
        achievement_display = ""
        if player_data['achievements']:
            latest_achievements = player_data['achievements'][-3:]  # Show last 3
            achievement_emojis = [self.achievements[ach]['name'].split()[0] for ach in latest_achievements]
            achievement_display = f"🏆 <b>Recent Badges:</b> {' '.join(achievement_emojis)}"
        
        # Special status indicators
        status_indicators = []
        if player_data['double_xp_remaining'] > 0:
            status_indicators.append(f"⭐ Double XP ({player_data['double_xp_remaining']} left)")
        if player_data['streak_shields'] > 0:
            status_indicators.append(f"🛡️ Streak Shield ({player_data['streak_shields']})")
        if player_data['lucky_charms'] > 0:
            status_indicators.append(f"🍀 Lucky Charm ({player_data['lucky_charms']})")
        
        status_text = "\n" + "\n".join([f"• {status}" for status in status_indicators]) if status_indicators else ""
        
        welcome_msg = f"""
🎮 <b>CRYPTO CLASH</b> 🎮
GM {username}! Ready to dominate the markets? 💎

⚡ <b>{level_display}</b>

🎯 <b>Game Stats:</b>
• Shard Tokens: {player_data['shard_tokens']:,} 💎
• Win Streak: {player_data['streak']} 🔥 (Best: {player_data['best_streak']})
• Whale Power-ups: {player_data['whale_powerups']} 🐋
• Achievements: {len(player_data['achievements'])}/7 🏆

{achievement_display}

{daily_challenge}

{og_msg}

{status_text}

🚀 <b>Quick Commands:</b>
• /predict - Start epic prediction
• /profile - Detailed stats & achievements  
• /shop - Power-up marketplace
• /daily - Check daily quest
• /leaderboard - Hall of legends

<i>LFG! Time to make some alpha moves! 🚀</i>
        """
        
        try:
            await update.message.reply_text(welcome_msg.strip(), parse_mode='HTML')
            logger.info(f"✅ Successfully sent welcome message to user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send welcome message to user {user_id}: {e}")

    async def predict_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new prediction"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "anon"
        
        logger.info(f"🎯 PREDICT COMMAND: User {user_id} ({username}) started prediction in chat {chat_id}")
        
        player_data = self.get_player_data(user_id)
        
        # Check if user has active prediction
        for pred_id, pred_data in self.active_predictions.items():
            if pred_data['user_id'] == user_id and not pred_data.get('completed', False):
                remaining_time = 60 - int(time.time() - pred_data['timestamp'])
                if remaining_time > 0:
                    await update.message.reply_text(
                        f"⏰ You already have an active prediction! {remaining_time}s remaining.\n"
                        f"💰 Predicting: {self.crypto_display[pred_data['crypto']]}\n"
                        f"🎯 Use /results to check status"
                    )
                    return
        
        # Check cooldown (longer for free API to avoid rate limits)
        api_key = os.getenv('COINGECKO_API_KEY')
        cooldown = 45 if not api_key else 30  # 45s for free, 30s for pro
        if time.time() - player_data['last_play'] < cooldown:
            remaining = int(cooldown - (time.time() - player_data['last_play']))
            tier = "Free" if not api_key else "Pro"
            await update.message.reply_text(f"⏰ Chill anon! {remaining}s cooldown remaining ({tier} tier)")
            return
        
        # Random FUD event (10% chance)
        fud_active = random.random() < 0.1
        fud_msg = f"\n🚨 **FUD EVENT:** {random.choice(self.fud_events)}" if fud_active else ""
        
        # Select random crypto
        crypto = random.choice(self.crypto_symbols)
        crypto_name = self.crypto_display[crypto]
        
        # Get current price
        current_price = await self.get_crypto_price(crypto)
        if not current_price:
            await update.message.reply_text(
                "🔧 Price oracle is down! Try again in a moment.\n"
                "The blockchain gods are testing our patience... 🙏"
            )
            return
        
        # Create prediction ID
        prediction_id = f"{user_id}_{int(time.time())}"
        
        # Store prediction data
        self.active_predictions[prediction_id] = {
            'user_id': user_id,
            'chat_id': chat_id,
            'crypto': crypto,
            'start_price': current_price,
            'timestamp': time.time(),
            'fud_active': fud_active,
            'locked': False,
            'completed': False
        }
        
        logger.info(f"Created prediction {prediction_id} for user {user_id}: {crypto_name} @ ${current_price}")
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📈 UP (+1%)", callback_data=f"predict_up_{prediction_id}"),
                InlineKeyboardButton("📉 DOWN (-1%)", callback_data=f"predict_down_{prediction_id}")
            ],
            [
                InlineKeyboardButton("🐋 WHALE MODE (3x)", callback_data=f"whale_{prediction_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        streak_bonus = f" | Streak: {player_data['streak']}🔥" if player_data['streak'] > 0 else ""
        og_emoji = "👑" if player_data['og_status'] else ""
        
        predict_msg = f"""
🎯 <b>PREDICTION TIME</b> {og_emoji}

💰 <b>{crypto_name}</b> | ${current_price:.4f}
⏰ <b>60 seconds</b> to predict 1%+ move!

💎 Shard Tokens: {player_data['shard_tokens']}{streak_bonus}
🐋 Whale Power-ups: {player_data['whale_powerups']}

{fud_msg}

Make your prediction! ⬇️
        """
        
        msg = await update.message.reply_text(predict_msg, reply_markup=reply_markup, parse_mode='HTML')
        
        # Schedule result check in 60 seconds with better error handling
        try:
            if context.job_queue is None:
                logger.error("JobQueue not available - results will not be automatically checked!")
                await update.message.reply_text(
                    "⚠️ **TECHNICAL ISSUE** ⚠️\n\n"
                    "Results won't auto-update. Use /results to check manually in 60s!\n"
                    "Your prediction is still valid! 🎯"
                )
                return
            
            context.job_queue.run_once(
                self.check_prediction_result,
                60,
                data={'prediction_id': prediction_id, 'message_id': msg.message_id, 'chat_id': chat_id},
                name=f"prediction_{prediction_id}"
            )
            logger.info(f"Scheduled result check for prediction {prediction_id}")
        except Exception as e:
            logger.error(f"Failed to schedule job for prediction {prediction_id}: {e}")
            await update.message.reply_text(
                "⚠️ **TIMER ISSUE** ⚠️\n\n"
                "Use /results to check your prediction result in 60 seconds!\n"
                "Your prediction is locked and will be processed! 🎯"
            )

    async def prediction_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle prediction button clicks with proper locking"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        username = query.from_user.username or "anon"
        
        logger.info(f"User {user_id} ({username}) clicked: {data}")
        
        if data.startswith('predict_'):
            parts = data.split('_')
            direction = parts[1]  # 'up' or 'down'
            prediction_id = '_'.join(parts[2:])
            
            if prediction_id not in self.active_predictions:
                await query.edit_message_text("⚠️ This prediction has expired!")
                return
            
            prediction = self.active_predictions[prediction_id]
            
            if prediction['user_id'] != user_id:
                await query.answer("🚫 This isn't your prediction!", show_alert=True)
                return
            
            # Check if already locked
            if prediction.get('locked', False):
                await query.answer("✅ Prediction already locked!", show_alert=True)
                return
            
            # Lock the prediction
            prediction['locked'] = True
            prediction['direction'] = direction
            prediction['predicted_at'] = time.time()
            
            direction_emoji = "📈" if direction == 'up' else "📉"
            crypto_name = self.crypto_display[prediction['crypto']]
            remaining_time = 60 - int(time.time() - prediction['timestamp'])
            
            logger.info(f"Locked prediction {prediction_id}: {direction} on {crypto_name}")
            
            locked_msg = f"""
✅ <b>PREDICTION LOCKED</b> ✅

💰 {crypto_name} {direction_emoji} {direction.upper()}
💵 Entry: ${prediction['start_price']:.4f}
⏰ Results in ~{max(0, remaining_time)}s
{'🐋 WHALE MODE ACTIVE (3x)' if prediction.get('whale_mode', False) else ''}

🤞 HODL tight! May the blockchain be with you! ⛓️

Use /results to check this prediction anytime!
            """
            
            await query.edit_message_text(locked_msg, parse_mode='HTML')
            
        elif data.startswith('whale_'):
            prediction_id = data[6:]  # Remove 'whale_' prefix
            await self.use_whale_powerup(query, prediction_id)

    async def use_whale_powerup(self, query, prediction_id: str):
        """Use whale power-up for 3x multiplier"""
        user_id = query.from_user.id
        player_data = self.get_player_data(user_id)
        
        if player_data['whale_powerups'] <= 0:
            await query.answer("🚫 No whale power-ups remaining!", show_alert=True)
            return
        
        if prediction_id not in self.active_predictions:
            await query.answer("⚠️ Prediction expired!", show_alert=True)
            return
        
        prediction = self.active_predictions[prediction_id]
        if prediction['user_id'] != user_id:
            await query.answer("🚫 Not your prediction!", show_alert=True)
            return
        
        if prediction.get('locked', False):
            await query.answer("⚠️ Prediction already locked!", show_alert=True)
            return
        
        # Consume whale power-up
        player_data['whale_powerups'] -= 1
        prediction['whale_mode'] = True
        
        crypto_name = self.crypto_display[prediction['crypto']]
        
        logger.info(f"User {user_id} activated whale mode for prediction {prediction_id}")
        
        # Update keyboard to show direction selection with whale mode
        keyboard = [
            [
                InlineKeyboardButton("🐋📈 WHALE UP (3x)", callback_data=f"predict_up_{prediction_id}"),
                InlineKeyboardButton("🐋📉 WHALE DOWN (3x)", callback_data=f"predict_down_{prediction_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🐋 <b>WHALE MODE ACTIVATED</b> 🐋\n\n"
            f"💰 {crypto_name} | ${prediction['start_price']:.4f}\n"
            f"⚡ <b>3x MULTIPLIER ACTIVE</b>\n"
            f"🎯 Pick your direction for massive gains!\n\n"
            f"🐋 Remaining Power-ups: {player_data['whale_powerups']}",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    async def check_prediction_result(self, context: ContextTypes.DEFAULT_TYPE):
        """Check prediction result after 60 seconds with comprehensive error handling"""
        job_data = context.job.data
        prediction_id = job_data['prediction_id']
        message_id = job_data['message_id']
        chat_id = job_data['chat_id']
        
        logger.info(f"Checking result for prediction {prediction_id}")
        
        if prediction_id not in self.active_predictions:
            logger.warning(f"Prediction {prediction_id} not found in active predictions")
            return
        
        prediction = self.active_predictions[prediction_id]
        
        # Mark as completed
        prediction['completed'] = True
        
        # Skip if no direction was selected
        if 'direction' not in prediction:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="⏰ <b>TIME'S UP!</b>\n\n🚫 No prediction made - you missed out anon!\n\nUse /predict to try again! 🚀",
                    parse_mode='HTML'
                )
                logger.info(f"Prediction {prediction_id} expired with no direction selected")
            except Exception as e:
                logger.error(f"Failed to update expired prediction message: {e}")
            
            # Store result for /results command
            prediction['result'] = 'expired'
            return
        
        # Get final price with retry
        final_price = await self.get_crypto_price(prediction['crypto'])
        if not final_price:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔧 <b>ERROR</b>\n\nPrice oracle failed - prediction cancelled!\nYour tokens and streak are safe! 💎\n\nUse /predict to try again!",
                    parse_mode='HTML'
                )
                logger.error(f"Failed to get final price for prediction {prediction_id}")
            except Exception as e:
                logger.error(f"Failed to update error message: {e}")
            
            # Store result for /results command
            prediction['result'] = 'error'
            prediction['error_msg'] = 'Price oracle failed'
            return
        
        # Calculate result
        start_price = prediction['start_price']
        price_change_pct = ((final_price - start_price) / start_price) * 100
        
        # Apply FUD difficulty
        required_change = 1.1 if prediction.get('fud_active', False) else 1.0
        
        # Determine if prediction was correct
        direction = prediction['direction']
        if direction == 'up':
            won = price_change_pct >= required_change
        else:
            won = price_change_pct <= -required_change
        
        # Update player data
        user_id = prediction['user_id']
        player_data = self.get_player_data(user_id)
        player_data['last_play'] = time.time()
        player_data['total_predictions'] += 1
        
        # Calculate rewards
        whale_multiplier = 3 if prediction.get('whale_mode', False) else 1
        streak_multiplier = 1 + (player_data['streak'] * 0.1)
        
        if won:
            player_data['wins'] += 1
            player_data['streak'] += 1
            player_data['perfect_streak'] += 1
            if player_data['streak'] > player_data['best_streak']:
                player_data['best_streak'] = player_data['streak']
            
            # Calculate token reward
            base_reward = 100
            total_reward = int(base_reward * whale_multiplier * streak_multiplier)
            player_data['shard_tokens'] += total_reward
            
            # Award XP (base 50 XP for wins)
            base_xp = 50 + (player_data['streak'] * 5)  # Bonus XP for streaks
            xp_result = self.award_xp(user_id, base_xp)
            
            # Update daily challenges
            self.update_daily_challenge(user_id, 'predictions')
            self.update_daily_challenge(user_id, 'win_streak', player_data['streak'])
            if whale_multiplier > 1:
                self.update_daily_challenge(user_id, 'whale_mode')
                player_data['whale_uses'] += 1
            
            # Check for new achievements
            new_achievements = self.check_achievements(user_id)
            
            response = random.choice(self.win_responses)
            
            # Build result message with gamification
            result_msg = f"""
🎉 <b>PREDICTION WON!</b> 🎉

{response}

📊 <b>Results:</b>
💰 {self.crypto_display[prediction['crypto']]}: ${start_price:.4f} → ${final_price:.4f}
📈 Change: {price_change_pct:+.2f}%
🎯 Needed: {'+' if direction == 'up' else '-'}{required_change}%

💎 <b>Rewards:</b>
• Shard Tokens: +{total_reward} 💎
• XP Gained: +{xp_result['awarded_xp']} ⚡{'🔥' if xp_result['double_xp_active'] else ''}
• Streak: {player_data['streak']} 🔥
{'• Whale Bonus: 3x 🐋' if whale_multiplier > 1 else ''}

💰 Total: {player_data['shard_tokens']:,} tokens | Level {xp_result['new_level']}
            """
            
            # Add level up notification
            if xp_result['level_up']:
                level_msg = random.choice(self.level_up_messages)
                result_msg += f"\n\n🎊 <b>{level_msg}</b>\n⚡ Welcome to Level {xp_result['new_level']}!"
            
            # Add achievement notifications
            if new_achievements:
                for ach_id in new_achievements:
                    ach = self.achievements[ach_id]
                    result_msg += f"\n\n🏆 <b>ACHIEVEMENT UNLOCKED!</b>\n{ach['name']} - {ach['desc']}\nReward: +{ach['reward']} tokens!"
            
            result_msg += "\n\nUse /predict for another round! 🚀"
            
            # Store result
            prediction['result'] = 'won'
            prediction['final_price'] = final_price
            prediction['price_change_pct'] = price_change_pct
            prediction['tokens_earned'] = total_reward
            prediction['xp_earned'] = xp_result['awarded_xp']
            
            # Update group leaderboard
            group_data = self.get_group_data(prediction['chat_id'])
            group_data['leaderboard'][user_id] = player_data['best_streak']
            
            # Check for streak announcements (every 5 wins)
            if player_data['streak'] >= 5 and player_data['streak'] % 5 == 0:
                await self.announce_achievement(context, prediction['chat_id'], user_id, player_data['streak'])
                
            logger.info(f"Prediction {prediction_id} WON - User {user_id} earned {total_reward} tokens, {xp_result['awarded_xp']} XP, streak: {player_data['streak']}")
                
        else:
            # Handle loss with streak shield protection
            previous_streak = player_data['streak']
            streak_protected = False
            
            if player_data['streak_shields'] > 0:
                player_data['streak_shields'] -= 1
                streak_protected = True
                protection_msg = "🛡️ <b>STREAK SHIELD ACTIVATED!</b> Your streak is protected!"
            else:
                player_data['streak'] = 0
                player_data['perfect_streak'] = 0
                protection_msg = ""
            
            # Still update daily challenges for attempts
            self.update_daily_challenge(user_id, 'predictions')
            if whale_multiplier > 1:
                player_data['whale_uses'] += 1
            
            # Award small XP for participation
            xp_result = self.award_xp(user_id, 10)
            
            response = random.choice(self.lose_responses)
            result_msg = f"""
💸 <b>PREDICTION LOST</b> 💸

{response}

📊 <b>Results:</b>
💰 {self.crypto_display[prediction['crypto']]}: ${start_price:.4f} → ${final_price:.4f}
📉 Change: {price_change_pct:+.2f}%
🎯 Needed: {'+' if direction == 'up' else '-'}{required_change}%

{protection_msg}

⚡ XP: +{xp_result['awarded_xp']} (participation bonus)
{'💔 Streak reset to 0' if not streak_protected else f'🔥 Streak preserved: {player_data["streak"]}'}
💎 Tokens: {player_data['shard_tokens']:,} 💎

Better luck next time! Use /predict to try again! 🍀
            """
            
            # Store result
            prediction['result'] = 'lost'
            prediction['final_price'] = final_price
            prediction['price_change_pct'] = price_change_pct
            prediction['previous_streak'] = previous_streak
            prediction['streak_protected'] = streak_protected
            prediction['xp_earned'] = xp_result['awarded_xp']
            
            logger.info(f"Prediction {prediction_id} LOST - User {user_id} lost streak of {previous_streak} (protected: {streak_protected})")
        
        # Send result with error handling
        try:
            message_id = job_data.get('message_id')
            if message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=result_msg,
                    parse_mode='HTML'
                )
                logger.info(f"Successfully sent result for prediction {prediction_id}")
            else:
                # Send as new message if no message_id (manual check)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎯 **PREDICTION RESULT**\n\n{result_msg}",
                    parse_mode='HTML'
                )
                logger.info(f"Sent new result message for prediction {prediction_id}")
        except Exception as e:
            logger.error(f"Failed to send result message for prediction {prediction_id}: {e}")
            # Try to send as new message if edit fails
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎯 **PREDICTION RESULT**\n\n{result_msg}",
                    parse_mode='HTML'
                )
            except Exception as e2:
                logger.error(f"Failed to send new result message: {e2}")

    async def results_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's recent prediction results"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "anon"
        
        # Find user's recent predictions
        user_predictions = []
        for pred_id, pred_data in self.active_predictions.items():
            if pred_data['user_id'] == user_id:
                user_predictions.append((pred_id, pred_data))
        
        if not user_predictions:
            await update.message.reply_text(
                "📊 **NO PREDICTIONS YET**\n\n"
                "You haven't made any predictions yet!\n"
                "Use /predict to start your first prediction! 🚀"
            )
            return
        
        # Sort by timestamp (most recent first)
        user_predictions.sort(key=lambda x: x[1]['timestamp'], reverse=True)
        
        results_text = f"📊 **{username}'s RECENT PREDICTIONS**\n\n"
        
        for i, (pred_id, pred_data) in enumerate(user_predictions[:5]):  # Show last 5
            crypto_name = self.crypto_display[pred_data['crypto']]
            
            if pred_data.get('completed', False):
                result = pred_data.get('result', 'unknown')
                if result == 'won':
                    status = f"✅ WON (+{pred_data.get('tokens_earned', 0)} tokens)"
                elif result == 'lost':
                    status = "❌ LOST"
                elif result == 'expired':
                    status = "⏰ EXPIRED"
                elif result == 'error':
                    status = "🔧 ERROR"
                else:
                    status = "❓ UNKNOWN"
                
                if 'final_price' in pred_data:
                    change = pred_data.get('price_change_pct', 0)
                    results_text += f"{i+1}. {crypto_name} ${pred_data['start_price']:.4f}→${pred_data['final_price']:.4f} ({change:+.2f}%) - {status}\n"
                else:
                    results_text += f"{i+1}. {crypto_name} ${pred_data['start_price']:.4f} - {status}\n"
            else:
                remaining_time = 60 - int(time.time() - pred_data['timestamp'])
                if remaining_time > 0:
                    direction = pred_data.get('direction', 'Not selected')
                    results_text += f"{i+1}. {crypto_name} ${pred_data['start_price']:.4f} - 🔄 ACTIVE ({direction}, {remaining_time}s left)\n"
                else:
                    results_text += f"{i+1}. {crypto_name} ${pred_data['start_price']:.4f} - ⏰ PENDING RESULT\n"
        
        results_text += "\nUse /predict to make a new prediction! 🎯"
        
        await update.message.reply_text(results_text, parse_mode='HTML')

    async def announce_achievement(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, streak: int):
        """Announce when someone achieves a milestone"""
        try:
            user = await context.bot.get_chat_member(chat_id, user_id)
            username = user.user.username or "anon"
            
            taunts = [
                f"🚨 @{username} just hit a {streak} streak! Who thinks they can beat this legend? 🏆",
                f"⚡ @{username} is absolutely dominating with {streak} wins! Step up or step aside! 💎",
                f"🔥 @{username} is on fire! {streak} predictions in a row! Anyone brave enough to challenge? 🎯",
                f"👑 All hail @{username}! {streak} streak achieved! The markets bow to your wisdom! 🧠"
            ]
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=random.choice(taunts),
                parse_mode='Markdown'
            )
            logger.info(f"Announced achievement for user {user_id} with {streak} streak")
        except Exception as e:
            logger.error(f"Failed to announce achievement: {e}")

    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group leaderboard"""
        chat_id = update.effective_chat.id
        group_data = self.get_group_data(chat_id)
        
        if not group_data['leaderboard']:
            await update.message.reply_text("🏆 No one has played yet! Use /predict to start the action!")
            return
        
        # Sort leaderboard by best streak
        sorted_leaders = sorted(
            group_data['leaderboard'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        leaderboard_text = "🏆 **CRYPTO CLASH LEADERBOARD** 🏆\n\n"
        
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        
        for i, (user_id, best_streak) in enumerate(sorted_leaders):
            try:
                user = await context.bot.get_chat_member(chat_id, user_id)
                username = user.user.username or f"Player{user_id}"
                player_data = self.get_player_data(user_id)
                og_emoji = " 👑" if player_data.get('og_status', False) else ""
                
                leaderboard_text += f"{medals[i]} **{username}**{og_emoji}\n"
                leaderboard_text += f"   Best Streak: {best_streak}🔥 | Tokens: {player_data['shard_tokens']}💎\n\n"
            except:
                continue
        
        leaderboard_text += f"👥 Total Players: {group_data['total_players']}\n"
        leaderboard_text += f"🎯 Use /predict to climb the ranks!"
        
        await update.message.reply_text(leaderboard_text, parse_mode='Markdown')

    async def challenge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Group vs group battles (enhanced)"""
        await update.message.reply_text(
            "⚔️ <b>GUILD WARS COMING SOON!</b> ⚔️\n\n"
            "🔥 Epic group vs group tournaments\n"
            "🏆 Massive rewards for winning guilds\n"
            "👑 Crown the ultimate trading guild\n\n"
            "Stay tuned for the ultimate crypto clash! 🚀",
            parse_mode='HTML'
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show player stats"""
        user_id = update.effective_user.id
        player_data = self.get_player_data(user_id)
        username = update.effective_user.username or "anon"
        
        win_rate = (player_data['wins'] / player_data['total_predictions'] * 100) if player_data['total_predictions'] > 0 else 0
        
        stats_msg = f"""
📊 **{username}'s STATS** {'👑' if player_data['og_status'] else ''} 📊

🎯 **Performance:**
• Total Predictions: {player_data['total_predictions']}
• Wins: {player_data['wins']}
• Win Rate: {win_rate:.1f}%
• Current Streak: {player_data['streak']}🔥
• Best Streak: {player_data['best_streak']}🏆

💰 **Assets:**
• Shard Tokens: {player_data['shard_tokens']}💎
• Whale Power-ups: {player_data['whale_powerups']}🐋
• Referrals: {player_data['referrals']}👥

Keep grinding anon! WAGMI! 🚀
        """
        
        await update.message.reply_text(stats_msg, parse_mode='Markdown')

    async def airdrop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Daily airdrop (referral simulation)"""
        user_id = update.effective_user.id
        player_data = self.get_player_data(user_id)
        
        # Simple daily bonus
        last_airdrop = player_data.get('last_airdrop', 0)
        if time.time() - last_airdrop < 86400:  # 24 hours
            remaining_hours = int((86400 - (time.time() - last_airdrop)) / 3600)
            await update.message.reply_text(f"🪂 Next airdrop in {remaining_hours}h! Share the bot for bonus tokens! 💎")
            return
        
        # Give airdrop
        airdrop_amount = random.randint(50, 200)
        player_data['shard_tokens'] += airdrop_amount
        player_data['last_airdrop'] = time.time()
        
        await update.message.reply_text(
            f"🪂 <b>DAILY AIRDROP</b> 🪂\n\n"
            f"GM anon! You received {airdrop_amount} Shard Tokens! 💎\n\n"
            f"💰 Total: {player_data['shard_tokens']:,} tokens\n\n"
            f"📢 Share this bot with friends for bonus airdrops!\n"
            f"http://t.me/CryptoClash12_Bot",
            parse_mode='HTML'
        )

    async def check_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually check prediction results (when JobQueue fails)"""
        user_id = update.effective_user.id
        
        # Find user's active predictions that should be completed
        completed_count = 0
        for pred_id, pred_data in self.active_predictions.items():
            if (pred_data['user_id'] == user_id and 
                not pred_data.get('completed', False) and 
                'direction' in pred_data and
                time.time() - pred_data['timestamp'] >= 60):
                
                # Manually trigger result check
                logger.info(f"Manually checking prediction {pred_id}")
                
                # Create fake context for the result check
                class FakeJob:
                    def __init__(self, data):
                        self.data = data
                
                class FakeContext:
                    def __init__(self, bot):
                        self.bot = bot
                        self.job = FakeJob({
                            'prediction_id': pred_id,
                            'message_id': None,  # Will be handled gracefully
                            'chat_id': pred_data['chat_id']
                        })
                
                fake_context = FakeContext(context.bot)
                await self.check_prediction_result(fake_context)
                completed_count += 1
        
        if completed_count > 0:
            await update.message.reply_text(f"✅ Checked {completed_count} pending prediction(s)!")
        else:
            await update.message.reply_text("📊 No pending predictions to check. Use /results to see your history!")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Log the error and gracefully shut down on conflict."""
        if isinstance(context.error, telegram.error.Conflict):
            logger.critical("CONFLICT ERROR: Another bot instance is running. Shutting down this instance.")
            # Emulate Ctrl+C to trigger graceful shutdown
            os.kill(os.getpid(), signal.SIGINT)
        else:
            logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    def calculate_level(self, xp: int) -> int:
        """Calculate player level based on XP"""
        for level in sorted(self.level_requirements.keys(), reverse=True):
            if xp >= self.level_requirements[level]:
                return level
        return 1

    def get_xp_for_next_level(self, current_level: int) -> int:
        """Get XP required for next level"""
        if current_level >= max(self.level_requirements.keys()):
            return 0
        return self.level_requirements[current_level + 1]

    def award_xp(self, user_id: int, base_xp: int) -> Dict:
        """Award XP and check for level up"""
        player_data = self.get_player_data(user_id)
        
        # Apply double XP if active
        multiplier = 2 if player_data['double_xp_remaining'] > 0 else 1
        awarded_xp = base_xp * multiplier
        
        if multiplier == 2:
            player_data['double_xp_remaining'] -= 1
        
        old_level = player_data['level']
        player_data['xp'] += awarded_xp
        new_level = self.calculate_level(player_data['xp'])
        player_data['level'] = new_level
        
        return {
            'awarded_xp': awarded_xp,
            'total_xp': player_data['xp'],
            'old_level': old_level,
            'new_level': new_level,
            'level_up': new_level > old_level,
            'double_xp_active': multiplier == 2
        }

    def check_achievements(self, user_id: int) -> List[str]:
        """Check and award new achievements"""
        player_data = self.get_player_data(user_id)
        new_achievements = []
        
        achievements_to_check = {
            'first_win': player_data['wins'] >= 1,
            'streak_5': player_data['best_streak'] >= 5,
            'streak_10': player_data['best_streak'] >= 10,
            'whale_user': player_data['whale_uses'] >= 10,
            'high_roller': player_data['shard_tokens'] >= 10000,
            'prophet': player_data['wins'] >= 100,
            'daily_warrior': player_data['daily_challenges_completed'] >= 7
        }
        
        for achievement_id, condition in achievements_to_check.items():
            if condition and achievement_id not in player_data['achievements']:
                player_data['achievements'].append(achievement_id)
                player_data['shard_tokens'] += self.achievements[achievement_id]['reward']
                new_achievements.append(achievement_id)
        
        return new_achievements

    def generate_daily_challenge(self, user_id: int):
        """Generate a new daily challenge for the user"""
        import random
        current_time = time.time()
        player_data = self.get_player_data(user_id)
        
        # Reset daily if 24 hours passed
        if current_time - player_data['last_challenge_reset'] > 86400:
            challenge = random.choice(self.challenge_types)
            self.daily_challenges[user_id] = {
                'type': challenge['type'],
                'desc': challenge['desc'],
                'progress': 0,
                'target': challenge['target'],
                'reward': challenge['reward'],
                'completed': False
            }
            player_data['last_challenge_reset'] = current_time
            player_data['perfect_streak'] = 0  # Reset perfect streak

    def update_daily_challenge(self, user_id: int, action: str, value: int = 1) -> bool:
        """Update daily challenge progress and return if completed"""
        if user_id not in self.daily_challenges:
            return False
        
        challenge = self.daily_challenges[user_id]
        if challenge['completed']:
            return False
        
        if challenge['type'] == action:
            challenge['progress'] += value
            if challenge['progress'] >= challenge['target']:
                challenge['completed'] = True
                player_data = self.get_player_data(user_id)
                player_data['shard_tokens'] += challenge['reward']
                player_data['daily_challenges_completed'] += 1
                return True
        
        return False

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed player profile with achievements and stats"""
        user_id = update.effective_user.id
        player_data = self.get_player_data(user_id)
        username = update.effective_user.username or "anon"
        
        # Calculate advanced stats
        win_rate = (player_data['wins'] / player_data['total_predictions'] * 100) if player_data['total_predictions'] > 0 else 0
        level_progress = self.get_xp_for_next_level(player_data['level'])
        
        # Achievement showcase
        achievement_text = "🏆 <b>Achievement Showcase:</b>\n"
        if player_data['achievements']:
            for ach_id in player_data['achievements']:
                ach = self.achievements[ach_id]
                achievement_text += f"• {ach['name']} - {ach['desc']}\n"
        else:
            achievement_text += "• No achievements yet - start predicting to unlock badges!\n"
        
        # Rank calculation (simplified)
        all_players = list(self.player_data.keys())
        rank = sorted(all_players, key=lambda x: self.player_data[x]['xp'], reverse=True).index(user_id) + 1
        
        profile_msg = f"""
👤 <b>{username}'s TRADING PROFILE</b> {'👑' if player_data['og_status'] else ''} 

⚡ <b>Level {player_data['level']}</b> | {player_data['xp']:,} XP
🏆 Global Rank: #{rank}

📊 <b>Performance Metrics:</b>
• Total Predictions: {player_data['total_predictions']}
• Wins: {player_data['wins']} | Win Rate: {win_rate:.1f}%
• Current Streak: {player_data['streak']} 🔥
• Best Streak: {player_data['best_streak']} 🏆
• Whale Mode Uses: {player_data['whale_uses']} 🐋

💎 <b>Wealth & Assets:</b>
• Shard Tokens: {player_data['shard_tokens']}💎
• Power-ups Owned: {player_data['whale_powerups']} 🐋
• Active Buffs: {sum([player_data['streak_shields'], player_data['double_xp_remaining'], player_data['lucky_charms']])}

{achievement_text}

📈 <b>Daily Progress:</b>
• Challenges Completed: {player_data['daily_challenges_completed']} ⚔️
• Perfect Prediction Streak: {player_data['perfect_streak']} ✨

<i>Keep grinding to unlock new achievements! 🚀</i>
        """
        
        await update.message.reply_text(profile_msg.strip(), parse_mode='HTML')

    async def shop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Power-up marketplace"""
        user_id = update.effective_user.id
        player_data = self.get_player_data(user_id)
        
        shop_msg = f"""
🛒 <b>POWER-UP MARKETPLACE</b> 🛒

💰 Your Balance: {player_data['shard_tokens']:,} tokens 💎

🛍️ <b>Available Power-ups:</b>

🐋 <b>Whale Mode</b> - 500 tokens
• 3x reward multiplier for next prediction
• Current stock: ∞

🛡️ <b>Streak Shield</b> - 1,000 tokens  
• Protects your streak from one loss
• Current stock: ∞

⭐ <b>Double XP Boost</b> - 300 tokens
• 2x XP for next 5 predictions  
• Current stock: ∞

🍀 <b>Lucky Charm</b> - 800 tokens
• Reduces required move to 0.5% for next prediction
• Current stock: ∞

<b>How to Buy:</b>
Reply with the power-up name to purchase!
Example: "Whale Mode" or "Lucky Charm"

<i>Invest wisely to dominate the markets! 📈</i>
        """
        
        await update.message.reply_text(shop_msg.strip(), parse_mode='HTML')

    async def daily_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show daily challenge status"""
        user_id = update.effective_user.id
        self.generate_daily_challenge(user_id)  # Ensure challenge exists
        
        if user_id not in self.daily_challenges:
            await update.message.reply_text("🎯 No daily challenge available. Try again tomorrow!")
            return
        
        challenge = self.daily_challenges[user_id]
        progress_bar = "█" * int((challenge['progress'] / challenge['target']) * 10)
        progress_bar += "░" * (10 - len(progress_bar))
        
        if challenge['completed']:
            status = "✅ <b>COMPLETED!</b> Reward claimed!"
            time_left = "New challenge in: Tomorrow!"
        else:
            status = f"🎯 <b>IN PROGRESS</b> [{progress_bar}] {challenge['progress']}/{challenge['target']}"
            hours_left = 24 - int((time.time() - self.get_player_data(user_id)['last_challenge_reset']) / 3600)
            time_left = f"Time remaining: {max(0, hours_left)} hours"
        
        daily_msg = f"""
⚔️ <b>DAILY CHALLENGE</b> ⚔️

🎯 <b>Today's Quest:</b>
{challenge['desc']}

{status}

💎 <b>Reward:</b> {challenge['reward']} Shard Tokens
⏰ <b>{time_left}</b>

<i>Complete daily challenges to unlock the Daily Warrior achievement! 🏆</i>
        """
        
        await update.message.reply_text(daily_msg.strip(), parse_mode='HTML')

    def run(self):
        """Start the bot"""
        try:
            # Build application with JobQueue enabled
            app = Application.builder().token(self.token).build()
            
            # Add the custom error handler to manage conflicts
            app.add_error_handler(self.error_handler)
            
            # Verify JobQueue is available
            if app.job_queue is None:
                logger.error("JobQueue not available! Predictions will not work properly.")
                print("❌ ERROR: JobQueue not set up. Install with: pip install 'python-telegram-bot[job-queue]'")
                return
            
            # Add handlers
            app.add_handler(CommandHandler("start", self.start_command))
            app.add_handler(CommandHandler("predict", self.predict_command))
            app.add_handler(CommandHandler("results", self.results_command))
            app.add_handler(CommandHandler("profile", self.profile_command))
            app.add_handler(CommandHandler("shop", self.shop_command))
            app.add_handler(CommandHandler("daily", self.daily_command))
            app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
            app.add_handler(CommandHandler("challenge", self.challenge_command))
            app.add_handler(CommandHandler("stats", self.stats_command))
            app.add_handler(CommandHandler("airdrop", self.airdrop_command))
            app.add_handler(CommandHandler("check", self.check_command))
            app.add_handler(CallbackQueryHandler(self.prediction_callback))
            
            logger.info("🚀 Crypto Clash Bot starting up! WAGMI! 🚀")
            logger.info(f"✅ JobQueue enabled: {app.job_queue is not None}")
            print("🚀 Crypto Clash Bot starting up! WAGMI! 🚀")
            print(f"✅ JobQueue enabled: {app.job_queue is not None}")
            
            # Run with better error handling and conflict resolution
            app.run_polling(
                drop_pending_updates=True,  # Clear any pending updates
                close_loop=False,
                allowed_updates=Update.ALL_TYPES  # Handle all update types
            )
            
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot shutting down gracefully due to signal.")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            print(f"❌ Bot startup failed: {e}")
            
            # Check for common issues
            if "Conflict" in str(e):
                print("\n💡 SOLUTION: Another bot instance is running!")
                print("• Stop all other instances of this bot")
                print("• Wait 30 seconds and try again")
                print("• Make sure only ONE instance runs at a time")
                print("• On Render: Restart your deployment")
            elif "Unauthorized" in str(e):
                print("\n💡 SOLUTION: Bot token issue!")
                print("• Check your TELEGRAM_BOT_TOKEN in .env")
                print("• Make sure the token is correct")
            else:
                print("\n💡 Check the error above and try again")
            
            raise

if __name__ == "__main__":
    bot = CryptoClashBot()
    bot.run() 