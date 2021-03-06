#!/usr/bin/env python3

import dataclasses

import homepose.libs.deployment
import homepose.libs.environment
import homepose.libs.networking
import homepose.libs.utils


@dataclasses.dataclass
class HomeposeInstance():
    enviroment: homepose.libs.environment.HomeposeDeployEnvironment = dataclasses.field(init=False, default_factory=homepose.libs.environment.HomeposeDeployEnvironment)
    networking: homepose.libs.networking.HomeposeNetworking = dataclasses.field(init=False, default_factory=homepose.libs.networking.HomeposeNetworking)
    deployment: homepose.libs.deployment.HomeposeDeployment = dataclasses.field(init=False, default_factory=homepose.libs.deployment.HomeposeDeployment)
    logging: homepose.libs.utils.HomeposeLogger = dataclasses.field(init=False)

    _currently_enabled_services: list = dataclasses.field(init=False, default_factory=list)
    _homepose_full_hostname: str = dataclasses.field(init=False, default='')

    def __post_init__(self) -> None:
        self.logging = homepose.libs.utils.HomeposeLogger()
        self._all_services = [
            self.enviroment['DATABASE_BACKEND'],
            *self.enviroment.get_enabled_services(),
            self.enviroment['REVERSE_PROXY_NAME']
        ]

    def start(self) -> None:
        self.logging.info('Mounting services directories')
        self.enviroment.mount_directories()
        self.logging.info('Starting up available services:')
        for service in self._all_services:
            self.enviroment.export_secret(service)
        self.deployment.compose_services(self._all_services, self.logging)
        self.logging.info('Configuring and enabling DNSMasq')
        self.networking.configure_dns()
        self.networking.broadcast_gateways(self.deployment.enviroment.get_enabled_services())

    def stop(self) -> None:
        self.logging.info(' Decomposing running services')
        self.deployment.remove_current_containers()
        self.logging.info(' Running containers purged!')

    def restart(self) -> None:
        self.logging.info('Stopping all running Docker services')
        self.stop()
        self.logging.info('Restarting docker network')
        self.deployment.restart_docker_network(
            self.enviroment['HOMEPOSE_DOCKER_NETWORK']
        )
        self.logging.info('Starting enabled Docker services')
        self.start()

    def add_external_service(self, ip_address: str, name: str) -> None:
        self.networking.add_gateway(ip_address, name)
