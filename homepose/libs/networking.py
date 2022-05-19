import dataclasses
import os
import shutil

import homepose.libs.environment
import homepose.libs.utils


@dataclasses.dataclass
class HomeposeNetworking():
    enviroment: homepose.libs.environment.HomeposeDeployEnvironment = dataclasses.field(init=False, default_factory=homepose.libs.environment.HomeposeDeployEnvironment)
    host_ip_address: str = dataclasses.field(init=False, default='')

    __additional_gateways: dict = dataclasses.field(init=False, default_factory=dict)
    __hosts_file_contents: str = dataclasses.field(init=False, default='')
    __reverse_proxy_location_template: str = dataclasses.field(init=False, default='')

    def __post_init__(self):  # sourcery skip: remove-redundant-if
        for line in os.popen('ip a show ${HOMEPOSE_ETHERNET_INTERFACE}').readlines():
            if 'inet ' and 'scope global dynamic' in line:  # pylint: disable=R1726
                self.host_ip_address = line.strip()[5:line.find('/')-4]
                os.environ.setdefault('HOMEPOSE_IP_ADDRESS', self.host_ip_address)
                os.environ.setdefault('HOSTNAME', os.popen('hostname').read().rstrip())
                break
        with open(homepose.libs.vars.HOSTS_TARGET_FILE_PATH, 'r') as current_hosts_file:
            self.__hosts_file_contents = current_hosts_file.read()
        with open(f'{self.enviroment["TEMPLATES_FOLDER"]}/configs/rproxy.location', 'r') as rproxy_location_template:
            self.__reverse_proxy_location_template = rproxy_location_template.read()

    def configure_dns(self):
        dnsmasq_install_result = os.popen('yes | apt-get install avahi-daemon').readlines()
        if 'E:' in dnsmasq_install_result[-1]:
            raise shutil.ExecError('Error setting up DNSMasq service')
        shutil.copyfile(f'{self.enviroment["GENERATED_FOLDER"]}/configs/dnsmasq.conf', homepose.libs.vars.DNSMASQ_CONF_TARGET_FILE_PATH)
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

        with open(homepose.libs.vars.HOSTS_TARGET_FILE_PATH, 'w') as current_hosts_file:
            current_hosts_file.truncate(0)
            current_hosts_file.write(new_hosts_file_contents)
