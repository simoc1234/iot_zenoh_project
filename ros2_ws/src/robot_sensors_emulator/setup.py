from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'robot_sensors_emulator'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='simone',
    maintainer_email='simone@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'imu_odom_publisher = robot_sensors_emulator.imu_odom_publisher:main',
            'proximity_publisher = robot_sensors_emulator.proximity_publisher:main',
            'camera_publisher = robot_sensors_emulator.camera_publisher:main',
            'ricevitore_velocita = robot_sensors_emulator.ricevitore_velocita:main',
        ],
    },
)
