import logging
import inspect
import os
from datetime import datetime
from colorama import Fore, init
import pprint
import traceback

init(autoreset=True)


class Logger:
    __logger = logging.getLogger(__name__)
    __logger.setLevel(logging.DEBUG)
    __handler = logging.StreamHandler()
    __formatter = logging.Formatter("%(message)s")
    __handler.setFormatter(__formatter)
    __logger.addHandler(__handler)

    @staticmethod
    def get_project_root():
        current_path = os.path.abspath(os.path.dirname(__file__))
        while True:
            # Check for common project root indicators
            if os.path.exists(os.path.join(current_path, 'setup.py')) or \
                    os.path.exists(os.path.join(current_path, 'pyproject.toml')) or \
                    os.path.exists(os.path.join(current_path, '.git')):
                return current_path

            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:
                # We've reached the root of the file system without finding a project root
                # In this case, we'll return the directory of the logger file itself
                return os.path.abspath(os.path.dirname(__file__))

            current_path = parent_path

    @staticmethod
    def __get_log_details():
        frame = inspect.stack()[3]
        file_name = frame.filename
        line_number = frame.lineno

        project_root = Logger.get_project_root()
        relative_file_name = os.path.relpath(file_name, project_root)
        relative_file_name = f"./{relative_file_name.replace(os.sep, '/')}"

        timestamp = datetime.utcnow().isoformat()
        pid = os.getpid()

        file_path_info = f"{relative_file_name}:{line_number}"
        return timestamp, pid, file_path_info

    @staticmethod
    def __log(message, details, level):
        timestamp, pid, file_path_info = Logger.__get_log_details()

        # Color the timestamp white
        colored_timestamp = f"{Fore.WHITE}{timestamp:<30}"

        # Color the log level according to its severity
        if level == logging.DEBUG:
            colored_log_level = f"{Fore.CYAN}{logging.getLevelName(level):<10}"
            colored_message = f"{Fore.CYAN}{message}"
        elif level == logging.INFO:
            colored_log_level = f"{Fore.GREEN}{logging.getLevelName(level):<10}"
            colored_message = f"{Fore.GREEN}{message}"
        elif level == logging.WARNING:
            colored_log_level = f"{Fore.YELLOW}{logging.getLevelName(level):<10}"
            colored_message = f"{Fore.YELLOW}{message}"
        elif level == logging.ERROR:
            colored_log_level = f"{Fore.RED}{logging.getLevelName(level):<10}"
            colored_message = f"{Fore.RED}{message}"
        else:
            colored_log_level = f"{Fore.MAGENTA}{logging.getLevelName(level):<10}"
            colored_message = f"{Fore.MAGENTA}{message}"

        # Color the file path white
        colored_file_path = f"{Fore.WHITE}{file_path_info:<40}"

        # Prepare the log message
        log_message = f"{colored_timestamp} {colored_log_level} {colored_file_path} : {colored_message}"

        # Pretty print details if provided
        if details is not None:
            if isinstance(details, Exception):
                # For exceptions, include the full stack trace
                error_details = ''.join(traceback.format_exception(type(details), details, details.__traceback__))
                log_message += f"\n{Fore.RED}{error_details}"
            else:
                # For other types of details, use pretty printing
                formatted_details = pprint.pformat(details, indent=4)
                log_message += f"\n{Fore.LIGHTWHITE_EX}{formatted_details}"

        # Log the message
        if level == logging.DEBUG:
            Logger.__logger.debug(log_message)
        elif level == logging.INFO:
            Logger.__logger.info(log_message)
        elif level == logging.WARNING:
            Logger.__logger.warning(log_message)
        elif level == logging.ERROR:
            Logger.__logger.error(log_message)
        elif level == logging.CRITICAL:
            Logger.__logger.critical(log_message)
        else:
            Logger.__logger.info(log_message)

    @staticmethod
    def debug(message, details=None):
        Logger.__log(message, details, logging.DEBUG)

    @staticmethod
    def info(message, details=None):
        Logger.__log(message, details, logging.INFO)

    @staticmethod
    def warn(message, details=None):
        Logger.__log(message, details, logging.WARNING)

    @staticmethod
    def error(message, details=None):
        Logger.__log(message, details, logging.ERROR)

    @staticmethod
    def critical(message, details=None):
        Logger.__log(message, details, logging.CRITICAL)
