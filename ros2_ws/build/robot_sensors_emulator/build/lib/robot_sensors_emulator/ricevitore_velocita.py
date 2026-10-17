import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class CmdVelListener(Node):
    def __init__(self):
        super().__init__('motor_controller_node')
        
        # Sottoscrizione al topic /cmd_vel con il tipo di messaggio Twist
        self.subscription = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.listener_callback,
            10)
            
        self.get_logger().info("Nodo motori avviato. In attesa di comandi di velocità su /cmd_vel...")

    def listener_callback(self, msg):
        # Stampa a schermo i valori ricevuti
        self.get_logger().info(
            f'Ricevuto Comando -> Avanti (X): {msg.linear.x} m/s | Rotazione (Z): {msg.angular.z} rad/s'
        )

def main(args=None):
    rclpy.init(args=args)
    node = CmdVelListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
