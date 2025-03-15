import json
import os
from datetime import datetime, timedelta

class CompetitionTracker:
    def __init__(self, config_file='competition.json'):
        self.config_file = config_file
        self.data = self.load_data()
        self.check_month_reset()

    def load_data(self):
        """Load competition data from file or initialize new"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self.initialize_new_data()
        return self.initialize_new_data()

    def initialize_new_data(self):
        """Create new competition data structure"""
        return {
            'last_reset': self.current_month_key(),
            'players': {},
            'pending': {}
        }

    def current_month_key(self):
        """Generate current month/year key"""
        now = datetime.now()
        return f"{now.year}-{now.month:02d}"

    def check_month_reset(self):
        """Reset data if new month has started"""
        current_key = self.current_month_key()
        if self.data['last_reset'] != current_key:
            self.data = self.initialize_new_data()
            self.save_data()

    def save_data(self):
        """Save data to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            print(f"Error saving competition data: {e}")

    def update_stats(self, players):
        """Update player statistics"""
        if not players:
            return
            
        self.check_month_reset()
        
        for player in players:
            if not hasattr(player, 'name') or not hasattr(player, 'score'):
                continue
                
            name = player.name.strip()
            if not name:
                continue
                
            if name not in self.data['players']:
                self.data['players'][name] = {
                    'score': 0,
                    'duration': 0,
                    'discord_id': None
                }
                
            self.data['players'][name]['score'] += player.score
            self.data['players'][name]['duration'] += player.duration
            
        self.save_data()

    def add_pending_request(self, discord_id, username):
        """Add new registration request"""
        if not discord_id or not username:
            return False
            
        username = username.strip()
        if not username:
            return False
            
        if username in self.data['players'] or username in self.data['pending']:
            return False
            
        self.data['pending'][username] = {
            'discord_id': str(discord_id),
            'timestamp': datetime.now().timestamp()
        }
        self.save_data()
        return True

    def approve_request(self, username):
        """Approve a registration request"""
        if username not in self.data['pending']:
            return False
            
        entry = self.data['pending'].pop(username)
        self.data['players'][username] = {
            'score': 0,
            'duration': 0,
            'discord_id': entry['discord_id']
        }
        self.save_data()
        return True

    def reject_request(self, username):
        """Reject a registration request"""
        if username in self.data['pending']:
            del self.data['pending'][username]
            self.save_data()
            return True
        return False

    def get_leaderboard(self, category='score', limit=5):
        """Get sorted leaderboard data"""
        valid_categories = ['score', 'duration']
        if category not in valid_categories:
            raise ValueError(f"Invalid category. Use: {', '.join(valid_categories)}")
            
        return sorted(
            self.data['players'].items(),
            key=lambda x: x[1][category],
            reverse=True
        )[:limit]

    def get_pending_requests(self):
        """Get all pending registration requests"""
        return self.data.get('pending', {})

    def get_discord_id(self, username):
        """Get Discord ID for a username"""
        return self.data['players'].get(username, {}).get('discord_id')

    def get_reset_date(self):
        """Get next reset date"""
        last_reset = datetime.strptime(self.data['last_reset'], "%Y-%m")
        next_reset = last_reset.replace(month=last_reset.month+1) if last_reset.month < 12 \
            else last_reset.replace(year=last_reset.year+1, month=1)
        return next_reset.strftime("%B %d, %Y")