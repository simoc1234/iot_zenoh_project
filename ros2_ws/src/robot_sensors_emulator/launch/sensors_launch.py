from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='robot_sensors_emulator',
            executable='imu_odom_publisher',
            name='imu_odom_publisher'
        ),
        Node(
            package='robot_sensors_emulator',
            executable='proximity_publisher',
            name='proximity_publisher'
        ),
        Node(
            package='robot_sensors_emulator',
            executable='camera_publisher',
            name='camera_publisher'
        ),
        Node(
            package='robot_sensors_emulator',
            executable='ricevitore_velocita',
            name='motor_controller_node',
            output='screen'
        )
    ])
