import dataclasses
import logging
import os
import shutil
import typing


@dataclasses.dataclass
class HomestackLogger():
    formatting: str = dataclasses.field(default=' %(name)s :: %(levelname)s :: %(message)s')
    level: int = dataclasses.field(default=logging.INFO)
    name: str = dataclasses.field(default='HOMEPOSE-SETUP')
    __logger: typing.Optional[logging.Logger] = dataclasses.field(init=False, default=None)
    __instance: dict = dataclasses.field(init=False, default_factory=dict)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_HomestackLogger__instance'):
            cls.__instance = {}
        if cls not in cls.__instance:
            logging.basicConfig()
            new_instance = super(HomestackLogger, cls).__new__(cls, *args, **kwargs)
            new_instance.__logger = cls.__init_logger()
            cls.__instance[cls] = new_instance
        return cls.__instance[cls]

    @classmethod
    def __init_logger(cls):
        logger = logging.getLogger(cls.name)
        logger.setLevel(cls.level)
        logger.propagate = False

        console_handler = logging.StreamHandler()
        console_handler.setLevel(cls.level)
        
        setup_log_formatter = logging.Formatter(fmt=cls.formatting)
        console_handler.setFormatter(setup_log_formatter)

        if (logger.hasHandlers()):
            logger.handlers.clear()
        logger.addHandler(console_handler)
        return logger

    def info(self, message: str):
        self.log(message, logging.INFO)

    def error(self, message: str):
        self.log(message, logging.ERROR)
    
    def warning(self, message: str):
        self.log(message, logging.WARNING)

    def debug(self, message: str):
        self.log(message, logging.DEBUG)

    def log(self, message: str, level: int):
        self.__logger.log(level, message)


def fill_templates(templates_path: str, generated_path: str):
    for subfolder in os.listdir(templates_path):
        for filename in os.listdir(f'{templates_path}/{subfolder}'):
            with open(f'{templates_path}/{subfolder}/{filename}', 'r') as template:
                filled_template = fill_template(template.read())
                with open(f'{generated_path}/{subfolder}/{filename}', 'w') as target_file:
                    target_file.truncate(0)
                    target_file.write(filled_template)
            shutil.chown(f'{generated_path}/{subfolder}/{filename}', user=os.environ['SUDO_USER'], group=os.environ['SUDO_USER'])


def fill_template(template_contents: str):
    for variable_name, variable_value in os.environ.items():
        entry_template_marker = f'[{variable_name}]'
        if entry_template_marker in template_contents:
            template_contents = template_contents.replace(entry_template_marker, variable_value) 
    return template_contents


def generate_dockerfile(template_path: str):
    service_name = template_path.split('/')[-1]
    with open(template_path, 'r') as dockerfile_template:
        return fill_template(dockerfile_template.read())
    return ''