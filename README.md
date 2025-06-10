# 🎮 Crypto Clash Bot 🚀

An addictive Telegram bot game where players predict short-term cryptocurrency price movements in viral, social gameplay loops.

## 🔥 Features

### Core Gameplay
- **⚡ 60-Second Predictions**: Quick rounds predicting 1%+ crypto price movements
- **🔥 Streak System**: Build consecutive wins for multiplier bonuses
- **💎 Shard Tokens**: Earn crypto-themed points for victories
- **🐋 Whale Power-ups**: 3x multiplier for high-stakes predictions
- **👑 OG Status**: First 10 players in each group get special privileges

### Social & Viral Mechanics
- **🏆 Group Leaderboards**: Auto-posted competitive rankings
- **🚨 Achievement Taunts**: Auto-generated challenges when players dominate
- **🪂 Daily Airdrops**: Free token rewards for engagement
- **📊 Performance Stats**: Win rates, streaks, and achievements

### Crypto Culture
- **Authentic Language**: Built-in crypto slang (WAGMI, REKT, GM, Diamond Hands)
- **🚨 FUD Events**: Random difficulty spikes with crypto-themed chaos
- **Real Price Data**: Live CoinGecko API integration
- **Multiple Cryptos**: BTC, ETH, BNB, ADA, SOL predictions

## 🛠️ Setup Instructions

### 1. Prerequisites
```bash
Python 3.8+
pip (Python package manager)
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Create Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow instructions to create your bot
4. Copy the bot token

### 4. Configure Environment
Create a `.env` file in the project directory:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 5. Run the Bot
```bash
python crypto_clash_bot.py
```

## 🎯 Commands

- `/start` - Welcome new players & show stats
- `/predict` - Start a new 60-second prediction round
- `/leaderboard` - View group rankings
- `/stats` - Show personal performance data
- `/airdrop` - Claim daily token rewards
- `/challenge` - Group vs group battles (coming soon)

## 🎮 How to Play

1. **Start**: Use `/predict` to begin a prediction
2. **Choose**: Select UP 📈 or DOWN 📉 for the crypto
3. **Power-up**: Optionally use Whale Mode for 3x rewards
4. **Wait**: 60 seconds for price movement resolution
5. **Rewards**: Earn Shard Tokens and build your streak!

## 🚀 Viral Mechanics

### Auto-Generated Taunts
When players hit milestones, the bot automatically posts challenges:
- "🚨 @user just hit a 5 streak! Who thinks they can beat this legend? 🏆"
- "⚡ @user is absolutely dominating! Step up or step aside! 💎"

### Social Pressure
- Public leaderboards create competition
- OG status for early adopters
- Achievement announcements in chat
- Daily airdrops encourage return visits

### Share-to-Unlock Features
- Referral-style bonuses for spreading the bot
- Group vs group competitive modes
- Exclusive power-ups for active communities

## 🔧 Technical Architecture

### Lightweight Design
- **In-Memory Storage**: Minimal data persistence
- **Free APIs**: CoinGecko for real crypto prices
- **Single File**: Easy deployment and modification
- **Async Operations**: Handles multiple concurrent predictions

### Data Stored Per User
```python
{
    'streak': 0,           # Current win streak
    'best_streak': 0,      # Personal record
    'shard_tokens': 1000,  # Virtual currency
    'whale_powerups': 1,   # Special abilities
    'og_status': False,    # First 10 in group
    'total_predictions': 0,
    'wins': 0
}
```

### Production Considerations
For production deployment, consider:
- Replace in-memory storage with Redis/PostgreSQL
- Add rate limiting and spam protection
- Implement data persistence
- Add monitoring and error tracking
- Scale horizontally with webhook mode

## 🎨 Customization

### Adding New Cryptos
Edit the `crypto_symbols` list in `crypto_clash_bot.py`:
```python
self.crypto_symbols = ['bitcoin', 'ethereum', 'your_new_crypto']
```

### Modifying Responses
Update the response arrays for different personality:
```python
self.win_responses = [
    "Your custom win message!",
    # Add more...
]
```

### Adjusting Game Balance
- Change prediction timeframe (default: 60 seconds)
- Modify required price movement (default: 1%)
- Adjust token rewards and multipliers
- Add new power-up types

## 🎯 Growth Strategy

### Organic Virality
1. **Seed Target Groups**: Crypto Telegram communities
2. **Leverage Existing Communities**: Join popular crypto groups
3. **Competitive Mechanics**: Leaderboards drive engagement
4. **Social Proof**: Public achievements and taunts

### Community Building
- Encourage group admins to add the bot
- Reward early adopters with OG status
- Create group vs group tournaments
- Regular feature updates and events

## 📈 Analytics & Optimization

Track these metrics for growth:
- Daily/Weekly active users
- Predictions per user per session
- Retention rates (1-day, 7-day, 30-day)
- Group adoption and viral coefficient
- Average session duration

## 🚨 Risk & Compliance

⚠️ **Important Notes:**
- This is a **game with virtual tokens**, not real cryptocurrency trading
- No real money or financial advice involved
- Players cannot lose actual funds
- Educational entertainment purpose only

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add your improvements
4. Test thoroughly
5. Submit pull request

## 📜 License

MIT License - feel free to modify and distribute

---

**WAGMI! Let's make crypto predictions fun and addictive! 🚀💎**

*Built with ❤️ for the crypto community* 