import dataclasses
import os
import shutil
import subprocess
import typing

import configparser

import homepose.libs.vars

class DeployConfigEmpty(Exception):
    default_message = 'Configuration is empty! Check your .ini file.' 
    def __init__(self, msg=default_message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class NonSudoCall(Exception):
    default_message = 'This module has to be run within script run with superuser privileges.' 
    def __init__(self, msg=default_message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


@dataclasses.dataclass
class HomestackDeployEnviroment():
    config_file_path: str = dataclasses.field(default=homepose.libs.vars.DEFAULT_CONFIG_FILE_PATH)
    www_data_username: str = dataclasses.field(default=homepose.libs.vars.DEFAULT_WWW_DATA_USER)
    www_data_userid: int = dataclasses.field(default=homepose.libs.vars.DEFAULT_WWW_DATA_USERID)
    www_data_groupid: int = dataclasses.field(default=homepose.libs.vars.DEFAULT_WWW_DATA_GROUPID)

    config: typing.Optional[dict] = dataclasses.field(init=False, default=None)
    __instance: dict = dataclasses.field(init=False, default_factory=dict)

    def __new__(cls, *args, **kwargs):
        if not os.geteuid() == 0:
            raise NonSudoCall()
        if not hasattr(cls, '_HomestackDeployEnviroment__instance'):
            cls.__instance = {}
        if cls not in cls.__instance:
            new_instance = super(HomestackDeployEnviroment, cls).__new__(cls, *args, **kwargs)
            new_instance.config = cls.parse_config_file(cls.config_file_path)
            new_instance.export_config()
            cls.__instance[cls] = new_instance
        return cls.__instance[cls]
    
    def __getitem__(self, key: str):
        return self.config.get(key)

    @staticmethod
    def parse_config_file(config_file_path: str) -> dict:
        config_file_contents = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
        config_file_contents.optionxform = str
        config_file_contents.read(config_file_path)
        denested_config = {}
        for section in config_file_contents.sections():
            for key, value in config_file_contents.items(section):
                denested_config[key] = value
        return denested_config

    def export_config(self) -> None:
        if not self.config:
            raise DeployConfigEmpty() 
        for setting_name, setting in self.config.items():
            self.update_env_var(setting_name, setting)
        for service in self.config['ENABLED_SERVICES'].split(','):
            self.update_env_var(f'{service.upper()}_COMPOSE_FILES_FOLDER',f'{self.config["COMPOSE_FILES_FOLDER"]}/{service}')

    @staticmethod	
    def update_env_var(key: str, value: str) -> None:
        if key not in os.environ:
            os.environ.setdefault(key, value)

    def setup_www_data_user(self) -> None:
        with open(os.devnull, 'w') as fp:
            popen_kwargs = {'stdout': fp, 'stderr': fp, 'shell': True}
            for command in [
                f'useradd -u {self.www_data_userid} {self.www_data_username}',
                f'groupadd -g {self.www_data_groupid} {self.www_data_username}',
                f'usermod -a -G {self.www_data_username} {self.www_data_username}'
            ]:
                subprocess.Popen(command, **popen_kwargs)
            os.environ['WWW_DATA_UID'] = self.www_data_userid
            os.environ['WWW_DATA_GID'] = self.www_data_groupid

    def export_secret(self, secret_name: str) -> None:
        secret = os.popen('openssl rand -hex 16').read().rstrip()
        os.environ[f'{secret_name.upper()}_SECRET'] = secret
    
    def mount_directories(self) -> None:
        for mount_name, mount in (
            (path_name, self.config[path_name])
            for path_name in list(self.config.keys())
            if '_MOUNT_POINT' in path_name
        ):
            os.makedirs(mount, exist_ok=True)
        os.makedirs(self.config['GENERATED_FOLDER'], exist_ok=True)
        os.makedirs(f'{self.config["GENERATED_FOLDER"]}/configs', exist_ok=True)
        os.makedirs(f'{self.config["GENERATED_FOLDER"]}/dockerfiles', exist_ok=True)
    
    def unmount_directories(self, force: bool = False) -> None:
        persistent_volumes = [] if force else os.environ['PERSISTENT_VOLUMES']
        for mount in (
            self.config[path_name]
            for path_name in list(self.config.keys())
            if '_MOUNT_POINT' in path_name
        ):
            if mount not in persistent_volumes and os.path.exists(mount):
                os.chown(mount, int(os.environ.get('SUDO_UID')), int(os.environ.get('SUDO_GID')))
                shutil.rmtree(mount, ignore_errors=True)
    
    def get_enabled_services(self):
        if enabled_services := self.config.get('ENABLED_SERVICES'): 
            return enabled_services.split(',')
        return []
