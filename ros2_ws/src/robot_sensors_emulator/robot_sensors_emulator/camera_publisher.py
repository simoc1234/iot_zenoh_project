import rclpy
from rclpy.node import Node
import numpy as np

from sensor_msgs.msg import Image

class CameraPublisher(Node):
    def __init__(self):
        super().__init__('camera_publisher')

        # Publisher per il topic standard delle immagini grezze
        self.image_pub = self.create_publisher(Image, '/camera/image_raw', 10)

        # Timer a 10 Hz (10 FPS simulati)
        self.timer = self.create_timer(0.1, self.publish_frame)

        # Dimensioni immagine sintetica (risoluzione contenuta per test di rete)
        self.height = 240
        self.width = 320
        self.step_counter = 0

        self.get_logger().info('Nodo Camera simulata avviato a 10 FPS.')

    def publish_frame(self):
        current_time = self.get_clock().now()

        # Genera un pattern dinamico (gradiente di colore RGB scorrevole)
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Animazione ciclica basata sul contatore di frame per simulare movimento
        shift = (self.step_counter * 5) % 256
        frame[:, :, 0] = (np.linspace(0, 255, self.width, dtype=np.uint8) + shift) % 256  # Canale Rosso
        frame[:, :, 1] = 120                                                              # Canale Verde fisso
        frame[:, :, 2] = (np.linspace(255, 0, self.height, dtype=np.uint8)[:, None] + shift) % 256 # Canale Blu
        
        self.step_counter += 1

        # Creazione del messaggio standard Image
        img_msg = Image()
        img_msg.header.stamp = current_time.to_msg()
        img_msg.header.frame_id = 'camera_optical_frame'
        img_msg.height = self.height
        img_msg.width = self.width
        img_msg.encoding = 'rgb8'
        img_msg.is_bigendian = 0
        img_msg.step = self.width * 3  # Dimensione di una riga in byte (larghezza * 3 canali colore)
        
        # Converte l'array numpy in un flusso di byte
        img_msg.data = frame.tobytes()

        self.image_pub.publish(img_msg)

def main(args=None):
    rclpy.init(args=args)
    node = CameraPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
