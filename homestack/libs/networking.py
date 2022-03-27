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
