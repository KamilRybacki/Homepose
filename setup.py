import setuptools

MODULE_NAME = 'homepose'

packages_list = [MODULE_NAME] + [
    f'{MODULE_NAME}.{package_name}'
    for package_name in setuptools.find_namespace_packages(where=MODULE_NAME)
]

setuptools.setup(
    name=MODULE_NAME,
    description='Automatic deployment of dockerized tech stack',
    author='Kamil Rybacki',
    packages=packages_list,
    python_requires='>=3.9',
    version='0.1',
    setup_requires=[
        'setuptools_scm'
    ],
    install_requires=[
        'docker==4.1.0',
        'configparser==5.2.0',
        'python-dotenv==0.19.2'
    ],
    zip_safe=False
)
