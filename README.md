![Homestack](/assets/logo.png)

# HomeStack <sub><sup>Yeah, it's that pop-culture reference</sup></sub>

In general terms, HomeStack is a Python module, which provides an interface
to quickly deploy Dockerized application using previously prepared
**Docker Compose `.yml` files**, **custom Dockerfiles** and **auxiliary Bash scripts**.

These files can be either hardcoded or dynamically generated with **templates**
created by user and automatically filled with appropiate enviroment variables.

These variables are exported by HomeStack on the basis of **`config.ini` file**,
located at the same location as a runner script using this module.

After deployment of available applications, they are advertised over local network
by use of automatically generated **DNSMasq** configuration read by Avahi zeroconf tools.

## Configuration file

The aforementioned `config.ini` file contains enviromental variables used during deployment
of user defined applications. 

For demonstration purposes, [`config_example.ini` file is located in a sister repo,
with my actual home lab stack](https://github.com/KamilRybacki/HomeStackComps). Please refer to that file. 

Below, config file sections are discussed with a special attention paid to entries,
which are **required** for HomeStack to function.

### `[BUILD]`

This section contains paths pointing to four **crucial** HomeStack directories:

1. Main folder containing directories with files for each of the desired apps - `COMPOSE_FILES_FOLDER`
2. Templates directory, that is used to generate deployment files - `TEMPLATES_FOLDER`
3. Target path for files created during the previous step - `GENERATED_FOLDER`
4. Directory, which contains other custom scripts e.g. Docker entrypoints - `CUSTOM_SCRIPTS_FOLDER`

By default, each of them is created based on the path provided with `BUILD_FOLDER` variable
i.e. are subfolders of the directory specified at `BUILD_FOLDER` location.
However, they can also be manually set to whatever path that the user wants.

### `[NETWORK]`

This section is used during generation of DNSMasq configuration files and controls
the way in which the end user can connect to services advertised by HomeStack.

A general name for the deployed architecture i.e. home lab is set with `HOMESTACK_NAME` variable.
Thin name is used during generation of internal Docker network (`HOMESTACK_DOCKER_NETWORK`)
and hostname used by Avahi during DNS server setup (`HOMESTACK_HOSTNAME`),
under domain specified in `HOMESTACK_DOMAIN` variable.

To establish connection with HomeStack server, default SSH port 
(`HOMESTACK_SSH_PORT`) and Ethernet interface (`HOMESTACK_ETHERNET_INTERFACE`) have to be set. 
Of course, other type of interface can be specified here, but it is **strongly** recommended to
use Ethernet connection instead of the wireless one, hence the variable name.

### `[PORTS]` and `[MOUNTS]`

Each new service has two types of variables used by them to function within HomeStack ecosystem.
Both are connected to the their deployment via Docker Compose - volumes and ports.

Let's assume that the name of the new service is `COOLAPP`. Its deployment requires two following variables
set:

`COOLAPP_PORT` - port under, which the service is available e.g. for Nginx serves that would be usually port 80
`COOLAPP_MOUNT` - mounting point, which maps host directory to a path inside spawned Docker container

If no volume is to be exposed, `COOLAPP_MOUNT` variable can be ommitted.
However, `COOLAPP_PORT` **has to be set** for proper reverse proxy setup,
because any requests made from the outside of Dockerized application need to be
properly redirected to a port within HomeStack host.

Wait, reverse proxy? Well, this is how HomeStack redirects requests resolved by DNSMasq service.
For example, DNSMasq resolves `coolapp.homestack.lan` to be `{host_ip_address}:[COOLAPP_PORT]`,
which is then redirected from `[COOLAPP_PORT]` of host server to `{ip_address_of_coolapp_container}:{port_within_container}`.

This is done thanks to [`nginx-proxy`](https://hub.docker.com/r/jwilder/nginx-proxy) Docker image by **jwilder**, so **MAJOR PROPS TO HIM**.
Please refer to its documentatio, because any Docker Compose files **NEED** special enviroment variables to be set.

Additionally, under `[MOUNTS]` section, directories, which should **never** be purged
(even if deletion of mounted volumes and their contents is initiated by `homestack` module)
can be specified using `PERSISTENT_VOLUMES` variable, where enviromental variables from the same
section can be listed (separated by whitespace).

### `[CREDENTIALS]`

Here, usernames and passwords for different services are stored.
If, by some chance, no authentication is needed anywhere, this section can be left empty.

However, connected with that topic is the automatic generation of 16 bytes pseudo-random hex secrets
for each new service. This can be useful for communication between specific services e.g. Drone and Gitea.
Each of those secrets can be accessed under `{service_name}_SECRET` enviromental variables.

### `[SERVICES]`

HomeStack, by default, enables all services listed in `ENABLED_SERVICES`, which allows for
faster debugging of chosen applications.

Name of directory used for setting up reverse proxy within HomeStack configuration is set
using `REVERSE_PROXY_NAME`, which means that under the path contained in `COMPOSE_FILES_FOLDER` variable
a folder named `REVERSE_PROXY_NAME` is present with previously prepared scripts and files.

A database backed to be used within HomeStack deployment is set with `DATABASE_BACKEND` variable.
Its functionality is same as with `REVERSE_PROXY_NAME` setting.

### Other sections

Users are free to create their own sections within configuration files, since they are used solely
to neatly organize HomeStack settings. In the `config_example.ini` file, `[MISC]` and `[ENTRYPOINTS]`
extra sections can be found and they are used by specific apps to carry out specific actions
e.g. setting Gitea app description string or specifying where a custom entrypoint is kept for Nextcloud.
In other words, sky is the limit.

## Why that and not just Docker Compose/Kubernetes/whatever?

First of all, the main goal set here by me was to learn about ins and outs of deploying services via Docker.
That's why I've chosen to write my own Python module for rapid development of deploy scripts. But...

Have You ever wanted to automatically carry out operations just before or after Docker Compose finished
its composing of a service? An example of such operation would be filesystem manipulations of mounted
Docker volumes i.e. modification of config files or changing permissions on chosen directories.

This can be done by creating `pre_init.sh` and `post_init.sh` Bash scripts, which are automagically
run by Homestack just before building of custom Dockerfiles. Wait, custom Dockerfiles?

Yeah, HomeStack checks if an app setup files directory contains a file named ... `Dockerfile`
and automatically build image defined there. This can be done manually or
by generation with the use of previously prepared templates. This makes the following magic possible:

1. Perform some sysadmin shinenigans and export a cool new enviroment variable name `SERVICE_VAR`, using `pre_init.sh` script.
2. Using Dockerfile template kept under `TEMPLATES_FOLDER` path, `[SERVICE_VAR]` text marker (see below) is substituted by the `SERVICE_VAR` value.
3. HomeStack build Docker image using the Dockerfile generated in step 2.
4. Docker Compose is then used to deploy whole service using `docker-compose.yml` file located in the same folder as `Dockerfile`
5. After that, a user wants to disable an annoying setting (untouchable normally by Docker Compose) by editing `config.php` file
inside a path mounted to Docker container directory. So, inside `post_init.sh` script, user can hardcode a string inside that file
e.g. `disable_stupid_setting => 'yes'` by echoing it via shell commands.

All without touching advanced Docker Compose features and by simply putting a couple of files inside a single folder.
HomeStack basically does all of the work glueing it all together and advertising it over a local network.

Can it be done via other tools? Probably yes. But these are my tools, I've learned a lot by making them and
if somebody want to use it - that would only add to my satisfaction from this project.

## Graphical representation HomeStack workflow

TO BE ARTISTICALLY DESIGNED
