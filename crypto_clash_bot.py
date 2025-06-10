import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
        
        # Crypto symbols for predictions
        self.crypto_symbols = ['bitcoin', 'ethereum', 'binancecoin', 'cardano', 'solana']
        self.crypto_display = {
            'bitcoin': 'BTC', 'ethereum': 'ETH', 'binancecoin': 'BNB', 
            'cardano': 'ADA', 'solana': 'SOL'
        }
        
        # Crypto slang responses
        self.win_responses = [
            "🚀 WAGMI! You just went to the moon!",
            "💎 Diamond hands paid off! Shard tokens incoming!",
            "🦍 Ape strong! Your streak is pumping!",
            "⚡ Lightning prediction! The market can't stop you!",
            "🔥 Absolutely based! You're built different!"
        ]
        
        self.lose_responses = [
            "😵 REKT! The market humbled you this time",
            "📉 Oof, that's a rug pull on your streak",
            "🤡 Paper hands move right there, anon",
            "💸 The market gods demand sacrifice",
            "⛔ Not your keys, not your gains... wait, wrong saying"
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
                'referrals': 0
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

    async def get_crypto_price(self, symbol: str, retries: int = 3) -> Optional[float]:
        """Fetch current crypto price from CoinGecko with API key and retry mechanism"""
        # Get API key from environment
        api_key = os.getenv('COINGECKO_API_KEY')
        
        for attempt in range(retries):
            try:
                logger.info(f"Fetching price for {symbol}, attempt {attempt + 1}")
                
                # Use Pro API if key is available, otherwise use free API
                if api_key:
                    url = f"https://pro-api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd&precision=6"
                    headers = {
                        'x-cg-pro-api-key': api_key,
                        'User-Agent': 'CryptoClash-Bot/1.0'
                    }
                    logger.info(f"Using CoinGecko Pro API with key for {symbol}")
                else:
                    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd&precision=6"
                    headers = {
                        'User-Agent': 'CryptoClash-Bot/1.0'
                    }
                    logger.info(f"Using CoinGecko Free API for {symbol}")
                
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                price = data[symbol]['usd']
                logger.info(f"Successfully fetched {symbol} price: ${price} (Pro API: {bool(api_key)})")
                return price
                
            except Exception as e:
                logger.error(f"Error fetching price for {symbol} (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(1.5 ** attempt)  # Shorter backoff with Pro API
                continue
        
        logger.error(f"Failed to fetch price for {symbol} after {retries} attempts")
        return None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - welcome new players"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "anon"
        
        logger.info(f"User {user_id} ({username}) started the bot in chat {chat_id}")
        
        player_data = self.get_player_data(user_id)
        group_data = self.get_group_data(chat_id)
        
        # Check for OG status (first 10 players in group)
        if not player_data['og_status'] and group_data['og_count'] < 10:
            player_data['og_status'] = True
            group_data['og_count'] += 1
            og_msg = "👑 Congratulations! You're now an OG in this group!"
            logger.info(f"User {user_id} got OG status in chat {chat_id}")
        else:
            og_msg = ""
        
        group_data['total_players'] = len(set(list(group_data['leaderboard'].keys()) + [user_id]))
        
        welcome_msg = f"""
🎮 **CRYPTO CLASH** 🎮
GM {username}! Ready to prove your diamond hands? 💎

🎯 **How to Play:**
• Predict if crypto goes UP ⬆️ or DOWN ⬇️ in 60 seconds
• Need 1%+ move to win
• Build streaks for multipliers! 
• Earn Shard Tokens 💎

💰 **Your Stats:**
• Shard Tokens: {player_data['shard_tokens']} 💎
• Best Streak: {player_data['best_streak']} 🔥
• Whale Power-ups: {player_data['whale_powerups']} 🐋

{og_msg}

Use /predict to start your first prediction!
Use /leaderboard to see who's dominating
Use /results to see your last prediction result

WAGMI! 🚀
        """
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def predict_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new prediction"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "anon"
        
        logger.info(f"User {user_id} ({username}) started prediction in chat {chat_id}")
        
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
        
        # Check cooldown (prevent spam)
        if time.time() - player_data['last_play'] < 30:
            remaining = int(30 - (time.time() - player_data['last_play']))
            await update.message.reply_text(f"⏰ Chill anon! {remaining}s cooldown remaining")
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
🎯 **PREDICTION TIME** {og_emoji}

💰 **{crypto_name}** | ${current_price:.4f}
⏰ **60 seconds** to predict 1%+ move!

💎 Shard Tokens: {player_data['shard_tokens']}{streak_bonus}
🐋 Whale Power-ups: {player_data['whale_powerups']}

{fud_msg}

Make your prediction! ⬇️
        """
        
        msg = await update.message.reply_text(predict_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Schedule result check in 60 seconds with better error handling
        try:
            context.job_queue.run_once(
                self.check_prediction_result,
                60,
                data={'prediction_id': prediction_id, 'message_id': msg.message_id, 'chat_id': chat_id},
                name=f"prediction_{prediction_id}"
            )
            logger.info(f"Scheduled result check for prediction {prediction_id}")
        except Exception as e:
            logger.error(f"Failed to schedule job for prediction {prediction_id}: {e}")

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
✅ **PREDICTION LOCKED** ✅

💰 {crypto_name} {direction_emoji} {direction.upper()}
💵 Entry: ${prediction['start_price']:.4f}
⏰ Results in ~{max(0, remaining_time)}s
{'🐋 WHALE MODE ACTIVE (3x)' if prediction.get('whale_mode', False) else ''}

🤞 HODL tight! May the blockchain be with you! ⛓️

Use /results to check this prediction anytime!
            """
            
            await query.edit_message_text(locked_msg, parse_mode='Markdown')
            
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
            f"🐋 **WHALE MODE ACTIVATED** 🐋\n\n"
            f"💰 {crypto_name} | ${prediction['start_price']:.4f}\n"
            f"⚡ **3x MULTIPLIER ACTIVE**\n"
            f"🎯 Pick your direction for massive gains!\n\n"
            f"🐋 Remaining Power-ups: {player_data['whale_powerups']}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
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
                    text="⏰ **TIME'S UP!**\n\n🚫 No prediction made - you missed out anon!\n\nUse /predict to try again! 🚀",
                    parse_mode='Markdown'
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
                    text="🔧 **ERROR**\n\nPrice oracle failed - prediction cancelled!\nYour tokens and streak are safe! 💎\n\nUse /predict to try again!",
                    parse_mode='Markdown'
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
            if player_data['streak'] > player_data['best_streak']:
                player_data['best_streak'] = player_data['streak']
            
            # Calculate token reward
            base_reward = 100
            total_reward = int(base_reward * whale_multiplier * streak_multiplier)
            player_data['shard_tokens'] += total_reward
            
            response = random.choice(self.win_responses)
            result_msg = f"""
🎉 **PREDICTION WON!** 🎉

{response}

📊 **Results:**
💰 {self.crypto_display[prediction['crypto']]}: ${start_price:.4f} → ${final_price:.4f}
📈 Change: {price_change_pct:+.2f}%
🎯 Needed: {'+' if direction == 'up' else '-'}{required_change}%

💎 **Rewards:**
• Shard Tokens: +{total_reward} 💎
• Streak: {player_data['streak']} 🔥
{'• Whale Bonus: 3x 🐋' if whale_multiplier > 1 else ''}

💰 Total Tokens: {player_data['shard_tokens']} 💎

Use /predict for another round! 🚀
            """
            
            # Store result
            prediction['result'] = 'won'
            prediction['final_price'] = final_price
            prediction['price_change_pct'] = price_change_pct
            prediction['tokens_earned'] = total_reward
            
            # Update group leaderboard
            group_data = self.get_group_data(prediction['chat_id'])
            group_data['leaderboard'][user_id] = player_data['best_streak']
            
            # Check for new leaderboard record
            if player_data['streak'] >= 5 and player_data['streak'] % 5 == 0:
                await self.announce_achievement(context, prediction['chat_id'], user_id, player_data['streak'])
                
            logger.info(f"Prediction {prediction_id} WON - User {user_id} earned {total_reward} tokens, streak: {player_data['streak']}")
                
        else:
            previous_streak = player_data['streak']
            player_data['streak'] = 0
            response = random.choice(self.lose_responses)
            result_msg = f"""
💸 **PREDICTION LOST** 💸

{response}

📊 **Results:**
💰 {self.crypto_display[prediction['crypto']]}: ${start_price:.4f} → ${final_price:.4f}
📉 Change: {price_change_pct:+.2f}%
🎯 Needed: {'+' if direction == 'up' else '-'}{required_change}%

💔 Streak reset to 0
💎 Tokens: {player_data['shard_tokens']} 💎

Better luck next time! Use /predict to try again! 🍀
            """
            
            # Store result
            prediction['result'] = 'lost'
            prediction['final_price'] = final_price
            prediction['price_change_pct'] = price_change_pct
            prediction['previous_streak'] = previous_streak
            
            logger.info(f"Prediction {prediction_id} LOST - User {user_id} lost streak of {previous_streak}")
        
        # Send result with error handling
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=result_msg,
                parse_mode='Markdown'
            )
            logger.info(f"Successfully sent result for prediction {prediction_id}")
        except Exception as e:
            logger.error(f"Failed to send result message for prediction {prediction_id}: {e}")
            # Try to send as new message if edit fails
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎯 **PREDICTION RESULT**\n\n{result_msg}",
                    parse_mode='Markdown'
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
        
        await update.message.reply_text(results_text, parse_mode='Markdown')

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
        """Start group vs group challenge"""
        await update.message.reply_text(
            "🔥 **GROUP BATTLES COMING SOON!** 🔥\n\n"
            "Soon you'll be able to challenge other Telegram groups!\n"
            "For now, focus on dominating your local leaderboard! 💪\n\n"
            "Use /predict to keep building your streak! 🚀"
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
            f"🪂 **DAILY AIRDROP** 🪂\n\n"
            f"GM anon! You received {airdrop_amount} Shard Tokens! 💎\n\n"
            f"💰 Total: {player_data['shard_tokens']} tokens\n\n"
            f"📢 Share this bot with friends for bonus airdrops!\n"
            f"http://t.me/CryptoClash12_Bot"
        )

    async def api_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show API status and features"""
        api_key = os.getenv('COINGECKO_API_KEY')
        
        if api_key:
            # Test Pro API connection
            try:
                test_price = await self.get_crypto_price('bitcoin')
                if test_price:
                    status_msg = f"""
🔥 **PRO API ACTIVE** 🔥

✅ **CoinGecko Pro Features:**
• Higher precision pricing (6 decimal places)
• Faster response times (< 500ms)
• 10,000 requests/month limit
• More reliable real-time data
• Priority support

💰 **Test Price:** BTC = ${test_price:,.6f}

🚀 **Performance Benefits:**
• Predictions are more accurate
• Less API failures
• Better user experience
• Shorter retry timeouts

Pro API Status: OPERATIONAL ✅
                    """
                else:
                    status_msg = "⚠️ Pro API key found but connection failed. Check your key!"
            except Exception as e:
                status_msg = f"❌ Pro API error: {str(e)}"
        else:
            status_msg = f"""
🆓 **FREE API MODE** 

ℹ️ **Current Features:**
• Basic price data
• 10-30 requests/minute limit
• Standard response times
• Good for testing

💡 **Upgrade to Pro API:**
• Add COINGECKO_API_KEY to environment
• Get higher rate limits
• Better reliability for predictions
• More precise pricing

API Status: FREE TIER ⚡
            """
        
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def enhanced_predict_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced prediction with Pro API features"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "anon"
        
        logger.info(f"User {user_id} ({username}) started enhanced prediction in chat {chat_id}")
        
        player_data = self.get_player_data(user_id)
        api_key = os.getenv('COINGECKO_API_KEY')
        
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
        
        # Check cooldown (reduced for Pro API users)
        cooldown = 20 if api_key else 30
        if time.time() - player_data['last_play'] < cooldown:
            remaining = int(cooldown - (time.time() - player_data['last_play']))
            await update.message.reply_text(f"⏰ Chill anon! {remaining}s cooldown remaining {'(Pro: 20s)' if api_key else ''}")
            return
        
        # Random FUD event (lower chance for Pro users)
        fud_chance = 0.08 if api_key else 0.1
        fud_active = random.random() < fud_chance
        fud_msg = f"\n🚨 **FUD EVENT:** {random.choice(self.fud_events)}" if fud_active else ""
        
        # Select random crypto
        crypto = random.choice(self.crypto_symbols)
        crypto_name = self.crypto_display[crypto]
        
        # Get current price with Pro API precision
        current_price = await self.get_crypto_price(crypto)
        if not current_price:
            await update.message.reply_text(
                "🔧 Price oracle is down! Try again in a moment.\n"
                "The blockchain gods are testing our patience... 🙏"
            )
            return
        
        # Create prediction ID
        prediction_id = f"{user_id}_{int(time.time())}"
        
        # Store prediction data with Pro API flag
        self.active_predictions[prediction_id] = {
            'user_id': user_id,
            'chat_id': chat_id,
            'crypto': crypto,
            'start_price': current_price,
            'timestamp': time.time(),
            'fud_active': fud_active,
            'locked': False,
            'completed': False,
            'pro_api': bool(api_key)
        }
        
        logger.info(f"Created prediction {prediction_id} for user {user_id}: {crypto_name} @ ${current_price} (Pro: {bool(api_key)})")
        
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
        pro_badge = " 🔥PRO" if api_key else ""
        
        # Enhanced precision display for Pro API
        if api_key:
            price_display = f"${current_price:,.6f}"
        else:
            price_display = f"${current_price:.4f}"
        
        predict_msg = f"""
🎯 **PREDICTION TIME**{pro_badge} {og_emoji}

💰 **{crypto_name}** | {price_display}
⏰ **60 seconds** to predict 1%+ move!
{'📊 Enhanced precision with Pro API!' if api_key else ''}

💎 Shard Tokens: {player_data['shard_tokens']}{streak_bonus}
🐋 Whale Power-ups: {player_data['whale_powerups']}

{fud_msg}

Make your prediction! ⬇️
        """
        
        msg = await update.message.reply_text(predict_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Schedule result check in 60 seconds with better error handling
        try:
            context.job_queue.run_once(
                self.check_prediction_result,
                60,
                data={'prediction_id': prediction_id, 'message_id': msg.message_id, 'chat_id': chat_id},
                name=f"prediction_{prediction_id}"
            )
            logger.info(f"Scheduled result check for prediction {prediction_id}")
        except Exception as e:
            logger.error(f"Failed to schedule job for prediction {prediction_id}: {e}")

    def run(self):
        """Start the bot"""
        app = Application.builder().token(self.token).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("predict", self.predict_command))
        app.add_handler(CommandHandler("results", self.results_command))
        app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        app.add_handler(CommandHandler("challenge", self.challenge_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("airdrop", self.airdrop_command))
        app.add_handler(CommandHandler("api_status", self.api_status_command))
        app.add_handler(CallbackQueryHandler(self.prediction_callback))
        
        logger.info("🚀 Crypto Clash Bot starting up! WAGMI! 🚀")
        print("🚀 Crypto Clash Bot starting up! WAGMI! 🚀")
        app.run_polling()

if __name__ == "__main__":
    bot = CryptoClashBot()
    bot.run() 