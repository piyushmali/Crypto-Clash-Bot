"""
Additional viral features for Crypto Clash Bot
These can be integrated into the main bot for enhanced social dynamics
"""

import random
import time
from typing import Dict, List, Optional

class ViralFeatures:
    """Additional social and viral mechanics for the bot"""
    
    def __init__(self):
        # Viral content templates
        self.challenge_templates = [
            "🚨 {username} just hit a {streak} streak! Drop a 🔥 if you think you can beat them!",
            "⚡ {username} is absolutely CRUSHING IT with {streak} wins! Who's brave enough to challenge? 💪",
            "🎯 BREAKING: {username} hit {streak} perfect predictions! The market bows to their wisdom 🧠",
            "🏆 {username} is on a {streak} win streak! Type '!challenge @{username}' to call them out!",
            "💎 Diamond hands alert! {username} just proved they're built different with {streak} wins!"
        ]
        
        self.group_war_taunts = [
            "🔥 GROUP WAR! {group1} vs {group2} - who has the better predictors? 👑",
            "⚔️ BATTLE ROYALE: {group1} thinks they're better than {group2}! Prove it! 🎯",
            "🚨 CHALLENGE ACCEPTED! {group1} vs {group2} prediction showdown starts NOW! ⏰"
        ]
        
        self.milestone_celebrations = {
            5: "🎉 First milestone! You're getting the hang of this!",
            10: "🔥 Double digits! The market is starting to fear you!",
            15: "⚡ Absolute unit! You're in the top 1% of predictors!",
            20: "🏆 LEGEND STATUS! Your prediction game is otherworldly!",
            25: "👑 CRYPTO ORACLE! The blockchain itself bows to you!",
            50: "🚀 TO THE MOON! You've transcended human prediction limits!",
            100: "💎 DIAMOND DEITY! You ARE the market!"
        }
        
        self.fomo_triggers = [
            "🚨 3 people just won in a row! Don't get left behind!",
            "⚡ Someone just made 500 Shard Tokens in one prediction! Your turn?",
            "🔥 This group is ON FIRE! Join the winning streak!",
            "💰 Whale alert! Big gains happening right now!",
            "🎯 The market is moving fast! Quick, make your prediction!"
        ]

    def generate_achievement_post(self, username: str, streak: int, tokens_earned: int = 0) -> str:
        """Generate viral achievement post"""
        template = random.choice(self.challenge_templates)
        post = template.format(username=username, streak=streak)
        
        if tokens_earned > 0:
            post += f"\n💎 Just earned {tokens_earned} Shard Tokens!"
        
        # Add milestone celebration
        if streak in self.milestone_celebrations:
            post += f"\n🎊 MILESTONE: {self.milestone_celebrations[streak]}"
        
        return post

    def create_group_challenge(self, group1_name: str, group2_name: str) -> str:
        """Generate group vs group challenge announcement"""
        template = random.choice(self.group_war_taunts)
        return template.format(group1=group1_name, group2=group2_name)

    def get_fomo_message(self) -> str:
        """Get a FOMO-inducing message to drive engagement"""
        return random.choice(self.fomo_triggers)

    def calculate_viral_score(self, player_data: Dict) -> int:
        """Calculate how viral-worthy a player's performance is"""
        score = 0
        
        # Streak contribution
        score += player_data.get('streak', 0) * 10
        
        # Win rate contribution
        total_predictions = player_data.get('total_predictions', 1)
        wins = player_data.get('wins', 0)
        win_rate = wins / total_predictions if total_predictions > 0 else 0
        score += int(win_rate * 100)
        
        # Recency bonus (played within last hour)
        last_play = player_data.get('last_play', 0)
        if time.time() - last_play < 3600:  # 1 hour
            score += 50
        
        return score

    def should_trigger_viral_post(self, player_data: Dict) -> bool:
        """Determine if a viral post should be triggered"""
        streak = player_data.get('streak', 0)
        
        # Always trigger on milestone streaks
        if streak in self.milestone_celebrations:
            return True
        
        # Random chance based on viral score
        viral_score = self.calculate_viral_score(player_data)
        threshold = 100  # Adjust this to control viral post frequency
        
        return viral_score > threshold and random.random() < 0.3

    def generate_referral_bonus_message(self, referrer: str, new_player: str) -> str:
        """Generate message for successful referrals"""
        messages = [
            f"🎉 {referrer} just brought {new_player} into the game! Both get 200 bonus Shard Tokens! 💎",
            f"🚀 Network effect! {referrer} expanded the Crypto Clash family! Welcome {new_player}! 👋",
            f"💪 {referrer} is building their army! {new_player} joined the prediction wars! ⚔️"
        ]
        return random.choice(messages)

    def create_daily_leaderboard_post(self, top_players: List[Dict]) -> str:
        """Generate daily leaderboard announcement"""
        if not top_players:
            return "🏆 No predictions yet today! Be the first to dominate! 🚀"
        
        post = "🏆 **DAILY LEADERBOARD** 🏆\n\n"
        medals = ["🥇", "🥈", "🥉"]
        
        for i, player in enumerate(top_players[:3]):
            medal = medals[i] if i < 3 else "🏅"
            username = player.get('username', 'Anonymous')
            streak = player.get('streak', 0)
            tokens = player.get('shard_tokens', 0)
            
            post += f"{medal} **{username}**\n"
            post += f"   Streak: {streak}🔥 | Tokens: {tokens}💎\n\n"
        
        post += "🎯 Think you can climb higher? Use /predict to start!\n"
        post += "💎 WAGMI! The market awaits your wisdom!"
        
        return post

    def generate_market_event_message(self) -> str:
        """Generate fake market event to drive engagement"""
        events = [
            "📈 BREAKING: Crypto markets pumping! Perfect time for predictions! 🚀",
            "📉 Market dip detected! Contrarian plays might pay off big! 💰",
            "⚡ High volatility incoming! Whale movements detected! 🐋",
            "🌙 Lunar cycle affecting crypto vibes! Mystical gains possible! ✨",
            "🤖 AI trading bots confused! Human intuition advantage activated! 🧠",
            "📊 Technical analysis says... actually, who cares! Trust your gut! 💪"
        ]
        return random.choice(events)

    def create_comeback_story(self, username: str, previous_streak: int, current_streak: int) -> str:
        """Generate comeback story for players who recover from losses"""
        return (f"🔥 COMEBACK STORY! 🔥\n\n"
                f"{username} went from {previous_streak} streak to {current_streak}!\n"
                f"Never give up! The market rewards persistence! 💪\n\n"
                f"Drop a 🚀 for this legend's resilience!")

# Utility functions for integration

def get_viral_content(feature_type: str, **kwargs) -> str:
    """Main function to get viral content"""
    vf = ViralFeatures()
    
    if feature_type == "achievement":
        return vf.generate_achievement_post(
            kwargs.get('username', ''),
            kwargs.get('streak', 0),
            kwargs.get('tokens_earned', 0)
        )
    elif feature_type == "group_challenge":
        return vf.create_group_challenge(
            kwargs.get('group1', ''),
            kwargs.get('group2', '')
        )
    elif feature_type == "fomo":
        return vf.get_fomo_message()
    elif feature_type == "referral":
        return vf.generate_referral_bonus_message(
            kwargs.get('referrer', ''),
            kwargs.get('new_player', '')
        )
    elif feature_type == "leaderboard":
        return vf.create_daily_leaderboard_post(
            kwargs.get('top_players', [])
        )
    elif feature_type == "market_event":
        return vf.generate_market_event_message()
    elif feature_type == "comeback":
        return vf.create_comeback_story(
            kwargs.get('username', ''),
            kwargs.get('previous_streak', 0),
            kwargs.get('current_streak', 0)
        )
    else:
        return "🚀 WAGMI! Keep predicting! 💎"

# Example usage:
if __name__ == "__main__":
    # Test viral features
    vf = ViralFeatures()
    
    print("🎮 Testing Viral Features:\n")
    
    # Test achievement post
    print("Achievement Post:")
    print(vf.generate_achievement_post("CryptoMaster", 15, 500))
    print()
    
    # Test group challenge
    print("Group Challenge:")
    print(vf.create_group_challenge("Diamond Hands", "Paper Hands"))
    print()
    
    # Test FOMO message
    print("FOMO Message:")
    print(vf.get_fomo_message())
    print()
    
    # Test viral score
    sample_player = {
        'streak': 12,
        'total_predictions': 20,
        'wins': 15,
        'last_play': time.time() - 1800  # 30 minutes ago
    }
    print(f"Viral Score: {vf.calculate_viral_score(sample_player)}")
    print(f"Should trigger viral: {vf.should_trigger_viral_post(sample_player)}") 