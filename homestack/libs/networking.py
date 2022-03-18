import dataclasses
import docker
import logging
import os
import shutil

import homestack.libs.enviroment
import homestack.libs.utils


class DNSMasqInstallError(Exception):
    default_message = 'DNSMasq installation failed!' 
    def __init__(self, msg=default_message, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


@dataclasses.dataclass
class HomestackNetworking():
    enviroment: homestack.libs.enviroment.HomestackDeployEnviroment = dataclasses.field(init=False, default_factory=homestack.libs.enviroment.HomestackDeployEnviroment)
    host_ip_address: str = dataclasses.field(init=False, default='')

    __additional_gateways: dict = dataclasses.field(init=False, default_factory=dict)
    __hosts_file_contents: str = dataclasses.field(init=False, default='')
    __reverse_proxy_location_template: str = dataclasses.field(init=False, default='')
    
    def __post_init__(self):
        for line in os.popen('ip a show ${HOMESTACK_ETHERNET_INTERFACE}').readlines():
            if 'inet ' and 'scope global dynamic' in line:
                self.host_ip_address = line.strip()[5:line.find('/')-4]
                os.environ.setdefault('HOMESTACK_IP_ADDRESS', self.host_ip_address)
                os.environ.setdefault('HOSTNAME', os.popen('hostname').read().rstrip())
                break
        with open(homestack.libs.vars.HOSTS_TARGET_FILE_PATH, 'r') as current_hosts_file: 
            self.__hosts_file_contents = current_hosts_file.read()
        with open(f'{self.enviroment["TEMPLATES_FOLDER"]}/configs/rproxy.location', 'r') as rproxy_location_template: 
            self.__reverse_proxy_location_template = rproxy_location_template.read()

    def configure_dns(self):
        dnsmasq_install_result = os.popen('yes | apt-get install avahi-daemon').readlines()
        if 'E:' in dnsmasq_install_result[-1]:
            raise DNSMasqInstallError()
        shutil.copyfile(f'{self.enviroment["GENERATED_FOLDER"]}/configs/dnsmasq.conf', homestack.libs.vars.DNSMASQ_CONF_TARGET_FILE_PATH)
        os.system('systemctl restart dnsmasq.service')

    def add_gateway(self, address: str, name: str):
        if address != self.host_ip_address:
            self.__additional_gateways[name] = address

    def broadcast_gateways(self, services_list: list):
        gateways_entries = [
            f'{additional_gateway_address} {additional_gateway_name}\n'
            for additional_gateway_name, additional_gateway_address in self.__additional_gateways.items()
        ] + [
            f'{self.host_ip_address} {service_name}\n'
            for service_name in services_list
        ]
        
        new_hosts_file_contents = self.__hosts_file_contents
        for entry in gateways_entries:
            if entry not in self.__hosts_file_contents:
                new_hosts_file_contents += entry
        
        current_hosts_file = open(homestack.libs.vars.HOSTS_TARGET_FILE_PATH, 'w')
        current_hosts_file.truncate(0)
        current_hosts_file.write(new_hosts_file_contents)
        current_hosts_file.close()

    @staticmethod
    def get_internal_ports(container_names: list, docker_instance: docker.client.DockerClient):
        internal_ports = {}
        for container_name in container_names:
            container = docker_instance.containers.get(container_name)
            container_info = container.image.attrs
            exposed_ports = [port.removesuffix('/tcp') for port in list(container_info['ContainerConfig']['ExposedPorts'].keys())]
            for port in exposed_ports:
                if port != '22' and port != '443':
                    internal_ports[container_name] = port
                    break
        return internal_ports

    def create_reverse_proxy_file(self, services: list, full_hostname: str, logger: logging.Logger = logging.Logger('R-PROXY')):
        locations_entries = ''
        for service_name in services:
            logger.info(f'  Advertising service {service_name} under path: {full_hostname}/{service_name}')
            service_port = self.enviroment[f'{service_name.upper()}_PORT']
            substituted_location_entry = self.__reverse_proxy_location_template\
                                        .replace('[SERVICE_NAME]', service_name.strip().rstrip())\
                                        .replace('[SERVICE_PORT]', service_port)
            locations_entries += f'\n{substituted_location_entry}'

        proxy_file_contents = f'''
        worker_processes 1;
        events {{ worker_connections 1024; }} 
        http {{
            
            proxy_set_header X-Real-IP  $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header Host $host;
            
            proxy_connect_timeout      90;
            proxy_send_timeout         90;
            proxy_read_timeout         90;

            server {{
                listen 80;
                server_name www.{full_hostname} {full_hostname};
                    {locations_entries}
            }}
        }}'''
        return proxy_file_contents