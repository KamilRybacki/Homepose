#!/usr/bin/env python3

import dataclasses

import homestack.libs.deployment
import homestack.libs.networking
import homestack.libs.utils

@dataclasses.dataclass
class HomestackInstance():
    enviroment: homestack.libs.enviroment.HomestackDeployEnviroment = dataclasses.field(init=False, default_factory=homestack.libs.enviroment.HomestackDeployEnviroment)
    networking: homestack.libs.networking.HomestackNetworking = dataclasses.field(init=False, default_factory=homestack.libs.networking.HomestackNetworking)
    deployment: homestack.libs.deployment.HomestackDeployment = dataclasses.field(init=False, default_factory=homestack.libs.deployment.HomestackDeployment)
    logging: homestack.libs.utils.HomestackLogger = dataclasses.field(init=False)

    _currently_enabled_services: list = dataclasses.field(init=False, default_factory=list)
    _homestack_full_hostname: str = dataclasses.field(init=False, default='')

    __REVERSE_PROXY_SERVICE_NAME: str = 'rproxy'

    def __post_init__(self):
        self.logging = homestack.libs.utils.HomestackLogger()
        self._all_services = [
            self.enviroment['DATABASE_BACKEND'],
            *self.enviroment.get_enabled_services(),
            self.enviroment['REVERSE_PROXY_NAME']
        ]

    def start(self):
        self.logging.info('Mounting services directories')
        self.enviroment.mount_directories()
        self.logging.info('Starting up available services:')
        for service in self._all_services:
            self.enviroment.export_secret(service)
        self.deployment.compose_services(self._all_services, self.logging)
        self.logging.info('Configuring and enabling DNSMasq')
        self.networking.configure_dns()
        self.networking.broadcast_gateways(self.deployment.enviroment.get_enabled_services())
        # target_reverse_proxy_file_path = f'{os.environ["RPROXY_MOUNT_POINT"]}/nginx.conf'
        # with open(target_reverse_proxy_file_path, 'w') as rproxy_conf:
        #     rproxy_conf.write(self.networking.create_reverse_proxy_file(
        #         self.enviroment.get_enabled_services(),
        #         self._homestack_full_hostname
        #     ))

    def stop(self):
        self.logging.info(' Decomposing running services')
        self.deployment.remove_current_containers()
        self.logging.info(' Running containers purged!')
    
    def restart(self):
        self.logging.info('Stopping all running Docker services')
        self.stop()
        self.logging.info('Restarting docker network')
        self.deployment.restart_docker_network(
            self.enviroment['HOMESTACK_DOCKER_NETWORK']
        )
        self.logging.info('Starting enabled Docker services')
        self.start()

    def add_external_service(self, ip_address: str, name: str):
        self.networking.add_gateway(ip_address, name)
