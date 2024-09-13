import requests
from typing import List, Tuple
import concurrent.futures
import random


class ProxyManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxyManager, cls).__new__(cls)
            cls._instance.proxies = []
        return cls._instance

    def initialize_proxies(self) -> None:
        """Initialize proxies from a text file."""
        self.proxies = []
        with open('proxies.txt', 'r') as file:
            for line in file:
                ip, port = line.strip().split(':')
                self.proxies.append((ip, int(port)))

        self.filter_working_proxies()

    def filter_working_proxies(self, timeout: int = 3) -> None:
        """Filter out non-working proxies."""

        def check_proxy(proxy: Tuple[str, int]) -> bool:
            try:
                response = requests.get('https://httpbin.org/ip',
                                        proxies={'http': f'http://{proxy[0]}:{proxy[1]}',
                                                 'https': f'http://{proxy[0]}:{proxy[1]}'},
                                        timeout=timeout)
                return response.status_code == 200
            except:
                return False

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(check_proxy, self.proxies))

        self.proxies = [proxy for proxy, is_working in zip(self.proxies, results) if is_working]

    def get_proxies(self) -> List[Tuple[str, int]]:
        """Get the list of working proxies."""
        return self.proxies

    def get_random_proxy(self) -> Tuple[str, int]:
        """Get a random proxy from the list of working proxies."""
        if not self.proxies:
            raise ValueError("No working proxies available.")
        return random.choice(self.proxies)
