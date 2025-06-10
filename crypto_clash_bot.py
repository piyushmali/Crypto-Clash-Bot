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

# Configure logging
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
        self.active_predictions = {}  # prediction_id: {user_id, chat_id, crypto, direction, start_price, timestamp}
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

    async def get_crypto_price(self, symbol: str) -> Optional[float]:
        """Fetch current crypto price from CoinGecko"""
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data[symbol]['usd']
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - welcome new players"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "anon"
        
        player_data = self.get_player_data(user_id)
        group_data = self.get_group_data(chat_id)
        
        # Check for OG status (first 10 players in group)
        if not player_data['og_status'] and group_data['og_count'] < 10:
            player_data['og_status'] = True
            group_data['og_count'] += 1
            og_msg = "👑 Congratulations! You're now an OG in this group!"
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
Use /challenge to battle other groups!

WAGMI! 🚀
        """
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def predict_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new prediction"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        player_data = self.get_player_data(user_id)
        
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
            await update.message.reply_text("🔧 Price oracle is down! Try again in a moment.")
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
            'fud_active': fud_active
        }
        
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
        
        # Schedule result check in 60 seconds
        context.job_queue.run_once(
            self.check_prediction_result,
            60,
            data={'prediction_id': prediction_id, 'message_id': msg.message_id},
            name=f"prediction_{prediction_id}"
        )

    async def prediction_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle prediction button clicks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
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
            
            # Store the prediction direction
            prediction['direction'] = direction
            prediction['predicted_at'] = time.time()
            
            direction_emoji = "📈" if direction == 'up' else "📉"
            crypto_name = self.crypto_display[prediction['crypto']]
            
            await query.edit_message_text(
                f"✅ **PREDICTION LOCKED** ✅\n\n"
                f"💰 {crypto_name} {direction_emoji} {direction.upper()}\n"
                f"💵 Entry: ${prediction['start_price']:.4f}\n"
                f"⏰ Results in ~{60 - int(time.time() - prediction['timestamp'])}s\n\n"
                f"🤞 HODL tight! May the blockchain be with you! ⛓️"
            )
            
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
        
        # Consume whale power-up
        player_data['whale_powerups'] -= 1
        prediction['whale_mode'] = True
        
        crypto_name = self.crypto_display[prediction['crypto']]
        
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
            reply_markup=reply_markup
        )

    async def check_prediction_result(self, context: ContextTypes.DEFAULT_TYPE):
        """Check prediction result after 60 seconds"""
        job_data = context.job.data
        prediction_id = job_data['prediction_id']
        message_id = job_data['message_id']
        
        if prediction_id not in self.active_predictions:
            return
        
        prediction = self.active_predictions[prediction_id]
        
        # Skip if no direction was selected
        if 'direction' not in prediction:
            try:
                await context.bot.edit_message_text(
                    chat_id=prediction['chat_id'],
                    message_id=message_id,
                    text="⏰ **TIME'S UP!**\n\n🚫 No prediction made - you missed out anon!"
                )
            except:
                pass
            del self.active_predictions[prediction_id]
            return
        
        # Get final price
        final_price = await self.get_crypto_price(prediction['crypto'])
        if not final_price:
            try:
                await context.bot.edit_message_text(
                    chat_id=prediction['chat_id'],
                    message_id=message_id,
                    text="🔧 **ERROR**\n\nPrice oracle failed - prediction cancelled!"
                )
            except:
                pass
            del self.active_predictions[prediction_id]
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
            """
            
            # Update group leaderboard
            group_data = self.get_group_data(prediction['chat_id'])
            group_data['leaderboard'][user_id] = player_data['best_streak']
            
            # Check for new leaderboard record
            if player_data['streak'] >= 5 and player_data['streak'] % 5 == 0:
                await self.announce_achievement(context, prediction['chat_id'], user_id, player_data['streak'])
                
        else:
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

Better luck next time! 🍀
            """
        
        # Send result
        try:
            await context.bot.edit_message_text(
                chat_id=prediction['chat_id'],
                message_id=message_id,
                text=result_msg
            )
        except:
            pass
        
        # Clean up
        del self.active_predictions[prediction_id]

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
        except:
            pass

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
            f"t.me/your_bot_username"
        )

    def run(self):
        """Start the bot"""
        app = Application.builder().token(self.token).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("predict", self.predict_command))
        app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        app.add_handler(CommandHandler("challenge", self.challenge_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("airdrop", self.airdrop_command))
        app.add_handler(CallbackQueryHandler(self.prediction_callback))
        
        print("🚀 Crypto Clash Bot starting up! WAGMI! 🚀")
        app.run_polling()

if __name__ == "__main__":
    bot = CryptoClashBot()
    bot.run() 