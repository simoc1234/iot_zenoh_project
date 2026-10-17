import rclpy
from rclpy.node import Node
import math
import random

from sensor_msgs.msg import LaserScan

class ProximitySensorPublisher(Node):
    def __init__(self):
        super().__init__('proximity_publisher')

        # Publisher per il topic standard /scan
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)

        # Frequenza tipica LiDAR: 10 Hz (intervallo di 0.1 s)
        self.timer = self.create_timer(0.1, self.publish_scan)

        # Parametri geometrici e operativi del LiDAR
        self.angle_min = -math.pi         # -180° in radianti
        self.angle_max = math.pi          # +180° in radianti (copertura 360°)
        self.angle_increment = math.radians(5.0)  # Risoluzione angolare: 1 lettura ogni 5°
        self.range_min = 0.15             # Portata minima: 15 cm
        self.range_max = 12.0             # Portata massima: 12 metri

        # Calcolo del numero di campioni per una rotazione completa (72 raggi)
        self.num_readings = int(round((self.angle_max - self.angle_min) / self.angle_increment))

        self.get_logger().info('Nodo Sensore di Prossimità (LaserScan) avviato.')

    def publish_scan(self):
        current_time = self.get_clock().now()

        scan_msg = LaserScan()
        scan_msg.header.stamp = current_time.to_msg()
        scan_msg.header.frame_id = 'laser_frame'

        scan_msg.angle_min = self.angle_min
        scan_msg.angle_max = self.angle_max
        scan_msg.angle_increment = self.angle_increment
        scan_msg.time_increment = 0.0
        scan_msg.scan_time = 0.1
        scan_msg.range_min = self.range_min
        scan_msg.range_max = self.range_max

        # Generazione delle letture simulate con rumore gaussiano
        ranges = []
        for i in range(self.num_readings):
            base_distance = 2.5 + 0.5 * math.sin(i * 0.1)
            noisy_distance = base_distance + random.uniform(-0.03, 0.03)
            ranges.append(float(noisy_distance))

        scan_msg.ranges = ranges
        self.scan_pub.publish(scan_msg)

        # Log diagnostico sintetico
        self.get_logger().info(f'LaserScan inviato: {len(ranges)} raggi | Distanza frontale: {ranges[0]:.2f} m')

def main(args=None):
    rclpy.init(args=args)
    node = ProximitySensorPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
