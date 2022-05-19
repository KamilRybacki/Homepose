import dataclasses
import logging
import os
import shutil
import typing


@dataclasses.dataclass
class HomeposeLogger():
    formatting: str = dataclasses.field(default=' %(name)s :: %(levelname)s :: %(message)s')
    level: int = dataclasses.field(default=logging.INFO)
    name: str = dataclasses.field(default='HOMEPOSE-SETUP')
    _logger: typing.Optional[logging.Logger] = dataclasses.field(init=False, default=None)
    _instance: dict = dataclasses.field(init=False, default_factory=dict)

    def __new__(cls, *args, **kwargs) -> 'HomeposeLogger':
        if not hasattr(cls, '_HomeposeLogger__instance'):
            cls._instance = {}
        if cls not in cls._instance:
            logging.basicConfig()
            new_instance = super(HomeposeLogger, cls).__new__(cls, *args, **kwargs)
            new_instance._logger = cls._init_logger()
            cls._instance[cls] = new_instance
        return cls._instance[cls]

    @classmethod
    def _init_logger(cls) -> 'HomeposeLogger':
        logger = logging.getLogger(cls.name)
        logger.setLevel(cls.level)
        logger.propagate = False

        console_handler = logging.StreamHandler()
        console_handler.setLevel(cls.level)

        setup_log_formatter = logging.Formatter(fmt=cls.formatting)
        console_handler.setFormatter(setup_log_formatter)

        if logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(console_handler)
        return logger

    def info(self, message: str) -> None:
        self.log(message, logging.INFO)

    def error(self, message: str) -> None:
        self.log(message, logging.ERROR)

    def warning(self, message: str) -> None:
        self.log(message, logging.WARNING)

    def debug(self, message: str) -> None:
        self.log(message, logging.DEBUG)

    def log(self, message: str, level: int) -> None:
        self._logger.log(level, message)


def fill_templates(templates_path: str, generated_path: str) -> None:
    for subfolder in os.listdir(templates_path):
        for filename in os.listdir(f'{templates_path}/{subfolder}'):
            with open(f'{templates_path}/{subfolder}/{filename}', 'r', encoding='utf8') as template:
                filled_template = fill_template(template.read())
                with open(f'{generated_path}/{subfolder}/{filename}', 'w', encoding='utf-8') as target_file:
                    target_file.truncate(0)
                    target_file.write(filled_template)
            shutil.chown(f'{generated_path}/{subfolder}/{filename}', user=os.environ['SUDO_USER'], group=os.environ['SUDO_USER'])


def fill_template(template_contents: str) -> str:
    for variable_name, variable_value in os.environ.items():
        entry_template_marker = f'[{variable_name}]'
        if entry_template_marker in template_contents:
            template_contents = template_contents.replace(entry_template_marker, variable_value)
    return template_contents


def generate_dockerfile(template_path: str) -> str:
    with open(template_path, 'r', encoding='utf-8') as dockerfile_template:
        return fill_template(dockerfile_template.read())
