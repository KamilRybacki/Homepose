#!/usr/bin/env python3

import dataclasses
import docker
import dotenv
import logging
import os
import shutil
import subprocess
import sys
import typing

import docker

import homestack.libs.vars
import homestack.libs.enviroment
import homestack.libs.utils


@dataclasses.dataclass
class HomestackDeployment():
    enviroment: homestack.libs.enviroment.HomestackDeployEnviroment = dataclasses.field(init=False, default_factory=homestack.libs.enviroment.HomestackDeployEnviroment)
    __logger: typing.Optional[str] = dataclasses.field(init=False, default=None)
    __instance: docker.client.DockerClient = dataclasses.field(default_factory=docker.from_env)
    __current_service_name: str = dataclasses.field(init=False, default='')
    __service_compose_path: str = dataclasses.field(init=False, default='')

    def remove_current_containers(self):
        all_current_containers = self.__instance.containers.list(all=True)
        for container in all_current_containers:
            container.remove(force=True)

    def restart_docker_network(self, network_name: str):
        try:
            network = self.__instance.networks.get(network_name)
            network.remove()
        except docker.errors.NotFound:
            pass
        self.__instance.networks.create(network_name)

    def compose_services(self, services_list: list, logger: logging.Logger = None):
        self.__logger = logging.Logger('COMPOSE') if not logger else logger
        homestack.libs.utils.fill_templates(
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
                network = self.__instance.networks.get(network_name)
                network.remove()
                raise Exception(f'Deployment of {service_name} failed!') 
            self.run_bash_script(f'{self.__service_compose_path}/post_init.sh')
        self.__logger = None

    def run_bash_script(self, script_path: str):
        if os.path.exists(script_path):
            self.run_with_popen(f'bash {script_path}', f'{script_path}.log')
    
    def run_with_popen(self, command: str, logpath: str):
        process = subprocess.Popen(
                    command, 
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
        process_output = [
            line.decode() 
            for line in process.communicate()
            if line.decode()
        ]
        if process.poll():
            return 1
        if len(process_output) > 0:
            with open(logpath, 'w') as script_log:
                script_log.writelines(process_output)
        return 0

    def compose_up(self, ignore_dockerfile: bool = False):
        self.source_additional_env_vars()
        self.build_docker_image()
        self.compose_currently_selected_service()

    def build_docker_image(self):
        dockerfile_template_path = f'{self.enviroment["TEMPLATES_FOLDER"]}/dockerfiles/{self.__current_service_name}'
        if os.path.exists(dockerfile_template_path):
            dockerfile_target_path = f'{self.__service_compose_path}/Dockerfile' 
            filled_dockerfile_template = homestack.libs.utils.generate_dockerfile(dockerfile_template_path)
            with open(dockerfile_target_path, 'w') as target_dockerfile:
                target_dockerfile.truncate(0)
                target_dockerfile.write(filled_dockerfile_template)
        if os.path.exists(f'{self.enviroment["COMPOSE_FILES_FOLDER"]}/{self.__current_service_name}/Dockerfile'):
            self.__logger.info(f'  Found custom Dockerfile for {self.__current_service_name}!')
            self.__logger.info(f'  Building Docker image ...')
            if self.run_with_popen(
                f'docker build -t custom-{self.__current_service_name} {self.__service_compose_path}', 
                f'{self.enviroment["COMPOSE_FILES_FOLDER"]}/{self.__current_service_name}/docker_build.log'
            ):
                raise Exception('Docker image build failed!')

    def source_additional_env_vars(self):
        dot_env_file_path = f'{self.__service_compose_path}/.env'
        if os.path.exists(dot_env_file_path):
            self.__logger.info(f'  Sourcing additional enviroment variables for {self.__current_service_name}!')
            dotenv.load_dotenv(dot_env_file_path)

    def compose_currently_selected_service(self):
        if self.__logger:
            self.__logger.info(f'  Composing Docker container for {self.__current_service_name}!')
        docker_compose_file_path = f'{self.__service_compose_path}/docker-compose.yml'
        self.compose_with_file(docker_compose_file_path)
    
    @staticmethod
    def compose_with_file(filepath: str):
        compose_process = subprocess.Popen(
            f'docker-compose -f {filepath} up -d', 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        compose_process_output = [line.decode() for line in compose_process.communicate()]
        if compose_process.poll():
            raise Exception(f'Deployment of service failed: {compose_process_output}')

    def compose_down(self):
        docker_compose_file_path = f'{self.__service_compose_path}/docker-compose.yml'
        try:
            process = subprocess.run(
                f'docker-compose -f {docker_compose_file_path} down', 
                shell=True,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError:
            raise Exception('Decomposition halted!')
