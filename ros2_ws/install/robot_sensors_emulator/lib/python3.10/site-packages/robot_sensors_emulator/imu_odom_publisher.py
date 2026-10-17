import rclpy
from rclpy.node import Node
import math

from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Quaternion

class ImuOdomPublisher(Node):
    def __init__(self):
        super().__init__('imu_odom_publisher')
        
        # Publisher sui topic standard ROS2
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 10)
        
        # Timer a 10 Hz (intervallo di 0.1 s)
        self.timer = self.create_timer(0.1, self.publish_telemetry)
        
        # Stato simulato del robot
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.linear_velocity = 0.2   # 0.2 m/s
        self.angular_velocity = 0.1  # 0.1 rad/s

        self.get_logger().info('Nodo IMU & Odometria avviato correttamente.')

    def publish_telemetry(self):
        current_time = self.get_clock().now()
        
        # Intervallo fisso per tick (0.1 s a 10 Hz)
        dt = 0.1

        # Aggiornamento cinematica stimata
        self.theta += self.angular_velocity * dt
        self.x += self.linear_velocity * math.cos(self.theta) * dt
        self.y += self.linear_velocity * math.sin(self.theta) * dt
        self.get_logger().info(f'Tick - x: {self.x:.2f}, y: {self.y:.2f}, theta: {self.theta:.2f}')
        # Conversione orientamento (Yaw -> Quaternion)
        qz = math.sin(self.theta / 2.0)
        qw = math.cos(self.theta / 2.0)

        # 1. Messaggio Odometry
        odom_msg = Odometry()
        odom_msg.header.stamp = current_time.to_msg()
        odom_msg.header.frame_id = 'odom'
        odom_msg.child_frame_id = 'base_link'
        
        odom_msg.pose.pose.position.x = float(self.x)
        odom_msg.pose.pose.position.y = float(self.y)
        odom_msg.pose.pose.position.z = 0.0
        odom_msg.pose.pose.orientation = Quaternion(x=0.0, y=0.0, z=qz, w=qw)
        
        odom_msg.twist.twist.linear.x = self.linear_velocity
        odom_msg.twist.twist.angular.z = self.angular_velocity
        
        self.odom_pub.publish(odom_msg)

        # 2. Messaggio IMU
        imu_msg = Imu()
        imu_msg.header.stamp = current_time.to_msg()
        imu_msg.header.frame_id = 'imu_link'
        imu_msg.orientation = Quaternion(x=0.0, y=0.0, z=qz, w=qw)
        imu_msg.angular_velocity.z = self.angular_velocity
        imu_msg.linear_acceleration.x = 0.0
        imu_msg.linear_acceleration.y = 0.0
        imu_msg.linear_acceleration.z = 9.81  # Accelerazione gravitazionale
        
        self.imu_pub.publish(imu_msg)

def main(args=None):
    rclpy.init(args=args)
    node = ImuOdomPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
