import json
from logger import Logger


class DataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance.filename = 'database.json'
            cls._instance.data = cls._instance.init()
        return cls._instance

    def init(self):
        Logger.info("Initializing DataManager")
        try:
            with open(self.filename, 'r') as file:
                data = json.load(file)
                data = {
                    'channels': set(data.get('channels', [])),
                    'monthly_sales_cutoff': data.get('monthly_sales_cutoff', 100)
                }
                Logger.debug('DataManager initialized with data:', data)
                return data
        except FileNotFoundError:
            Logger.warn(f"Database file {self.filename} not found. Initializing with empty data.")
            return {'channels': set(), 'monthly_sales_cutoff': 100}
        except json.JSONDecodeError as error:
            Logger.error('Error initializing DataManager:', error)
            raise

    def save(self):
        Logger.info("Saving data to file")
        try:
            with open(self.filename, 'w') as file:
                json.dump({
                    'channels': list(self.data['channels']),
                    'monthly_sales_cutoff': self.data['monthly_sales_cutoff']
                }, file, indent=2)
        except IOError as error:
            Logger.error('Error saving data:', error)
            raise

    def add_notification_channel(self, channel_id):
        """Add a channel ID for notifications."""
        Logger.info(f"Adding notification channel: {channel_id}")
        self.data['channels'].add(channel_id)
        self.save()

    def remove_notification_channel(self, channel_id):
        """Remove a channel ID from notifications."""
        Logger.info(f"Removing notification channel: {channel_id}")
        self.data['channels'].discard(channel_id)
        self.save()

    def get_notification_channels(self):
        """Get all channel IDs for notifications."""
        return list(self.data['channels'])

    def set_monthly_sales_cutoff(self, cutoff):
        """Set the minimum monthly sales cutoff."""
        Logger.info(f"Setting monthly sales cutoff: {cutoff}")
        self.data['monthly_sales_cutoff'] = cutoff
        self.save()

    def get_monthly_sales_cutoff(self):
        """Get the minimum monthly sales cutoff."""
        return self.data['monthly_sales_cutoff']
