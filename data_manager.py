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
                return {
                    'channel': data.get('channel', None),
                    'monthly_sales_cutoff': data.get('monthly_sales_cutoff', 100)
                }
        except FileNotFoundError:
            Logger.warn(f"Database file {self.filename} not found. Initializing with empty data.")
            return {'channel': None, 'monthly_sales_cutoff': 100}
        except json.JSONDecodeError as error:
            Logger.error('Error initializing DataManager:', error)
            raise

    def save(self):
        Logger.info("Saving data to file")
        try:
            with open(self.filename, 'w') as file:
                json.dump({
                    'channel': self.data['channel'],
                    'monthly_sales_cutoff': self.data['monthly_sales_cutoff']
                }, file, indent=2)
        except IOError as error:
            Logger.error('Error saving data:', error)
            raise

    def set_notification_channel(self, channel_id):
        """Set the channel ID for notifications."""
        Logger.info(f"Setting notification channel: {channel_id}")
        self.data['channel'] = channel_id
        self.save()

    def get_notification_channel(self):
        """Get the channel ID for notifications."""
        return self.data['channel']

    def set_monthly_sales_cutoff(self, cutoff):
        """Set the minimum monthly sales cutoff."""
        Logger.info(f"Setting monthly sales cutoff: {cutoff}")
        self.data['monthly_sales_cutoff'] = cutoff
        self.save()

    def get_monthly_sales_cutoff(self):
        """Get the minimum monthly sales cutoff."""
        return self.data['monthly_sales_cutoff']
