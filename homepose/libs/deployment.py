#!/usr/bin/env python3

import contextlib
import dataclasses
import logging
import os
import shutil
import subprocess
import typing

import dotenv
import docker

import homepose.libs.vars
import homepose.libs.environment
import homepose.libs.utils


@dataclasses.dataclass
class HomeposeDeployment():
    enviroment: homepose.libs.environment.HomeposeDeployEnvironment = dataclasses.field(init=False, default_factory=homepose.libs.environment.HomeposeDeployEnvironment)
    __logger: typing.Optional[str] = dataclasses.field(init=False, default=None)
    __instance: docker.client.DockerClient = dataclasses.field(default_factory=docker.from_env)
    __current_service_name: str = dataclasses.field(init=False, default='')
    __service_compose_path: str = dataclasses.field(init=False, default='')

    def remove_current_containers(self) -> None:
        all_current_containers = self.__instance.containers.list(all=True)
        for container in all_current_containers:
            container.remove(force=True)

    def restart_docker_network(self, network_name: str) -> None:
        with contextlib.suppress(docker.errors.NotFound):
            network = self.__instance.networks.get(network_name)
            network.remove()
        self.__instance.networks.create(network_name)

    def compose_services(self, services_list: list, logger: logging.Logger = None) -> None:
        self.__logger = logger or logging.Logger('COMPOSE')
        homepose.libs.utils.fill_templates(
            self.enviroment["TEMPLATES_FOLDER"],
            self.enviroment["GENERATED_FOLDER"]
        )
        for service_name in services_list:
            logger.info(f' Enabling service: {service_name}... ')
            self.__current_service_name = service_name
            self.__service_compose_path = f'{self.enviroment["COMPOSE_FILES_FOLDER"]}/{service_name}'
            self.run_bash_script(f'{self.__service_compose_path}/pre_init.sh')
            if self.compose_up():
                self.remove_current_containers()
                network_name = self.enviroment["HOMEPOSE_DOCKER_NETWORK"]
                network = self.__instance.networks.get(network_name)
                network.remove()
                raise shutil.ExecError(f'Deployment of {service_name} failed!')
            self.run_bash_script(f'{self.__service_compose_path}/post_init.sh')
        self.__logger = None

    def run_bash_script(self, script_path: str) -> None:
        if os.path.exists(script_path):
            self.run_with_popen(f'bash {script_path}', f'{script_path}.log')

    @staticmethod
    def run_with_popen(command: str, logpath: str) -> int:
        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            process_output = [
                line.decode()
                for line in process.communicate()
                if line.decode()
            ]
            if process.poll():
                return 1
            if process_output:
                with open(logpath, 'w', encoding='utf-8') as script_log:
                    script_log.writelines(process_output)
        return 0

    def compose_up(self, ignore_dockerfile: bool = False) -> None:
        self.source_additional_env_vars()
        if not ignore_dockerfile:
            self.build_docker_image()
        self.compose_currently_selected_service()

    def build_docker_image(self) -> None:
        dockerfile_template_path = f'{self.enviroment["TEMPLATES_FOLDER"]}/dockerfiles/{self.__current_service_name}'
        if os.path.exists(dockerfile_template_path):
            dockerfile_target_path = f'{self.__service_compose_path}/Dockerfile'
            filled_dockerfile_template = homepose.libs.utils.generate_dockerfile(dockerfile_template_path)
            with open(dockerfile_target_path, 'w', encoding='utf-8') as target_dockerfile:
                target_dockerfile.truncate(0)
                target_dockerfile.write(filled_dockerfile_template)
        if os.path.exists(f'{self.enviroment["COMPOSE_FILES_FOLDER"]}/{self.__current_service_name}/Dockerfile'):
            self.__logger.info(f'  Found custom Dockerfile for {self.__current_service_name}!')
            self.__logger.info('  Building Docker image ...')
            if self.run_with_popen(
                f'docker build -t custom-{self.__current_service_name} {self.__service_compose_path}',
                f'{self.enviroment["COMPOSE_FILES_FOLDER"]}/{self.__current_service_name}/docker_build.log'
            ):
                raise shutil.ExecError('Docker image build failed!')

    def source_additional_env_vars(self) -> None:
        dot_env_file_path = f'{self.__service_compose_path}/.env'
        if os.path.exists(dot_env_file_path):
            self.__logger.info(f'  Sourcing additional enviroment variables for {self.__current_service_name}!')
            dotenv.load_dotenv(dot_env_file_path)

    def compose_currently_selected_service(self) -> None:
        if self.__logger:
            self.__logger.info(f'  Composing Docker container for {self.__current_service_name}!')
        docker_compose_file_path = f'{self.__service_compose_path}/docker-compose.yml'
        self.compose_with_file(docker_compose_file_path)

    @staticmethod
    def compose_with_file(filepath: str) -> None:
        compose_command = f'docker-compose -f {filepath} up -d'
        with subprocess.Popen(compose_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as compose_process:
            compose_process_output = [line.decode() for line in compose_process.communicate()]
            if compose_process.poll():
                raise shutil.ExecError(f'Deployment of service failed: {compose_process_output}')

    def compose_down(self) -> None:
        docker_compose_file_path = f'{self.__service_compose_path}/docker-compose.yml'
        try:
            _ = subprocess.run(
                f'docker-compose -f {docker_compose_file_path} down',
                shell=True,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as encountered_exception:
            raise shutil.ExecError('Decomposition halted!') from encountered_exception
