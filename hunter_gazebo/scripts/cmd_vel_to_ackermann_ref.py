#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped


class CmdVelToAckermannRef(Node):
    def __init__(self) -> None:
        super().__init__('cmd_vel_to_ackermann_ref')

        self.declare_parameter('input_topic', '/cmd_vel')
        self.declare_parameter('output_topic', '/ackermann_like_controller/reference')
        self.declare_parameter('frame_id', 'base_link')

        input_topic = self.get_parameter('input_topic').get_parameter_value().string_value
        output_topic = self.get_parameter('output_topic').get_parameter_value().string_value
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value

        self.sub = self.create_subscription(
            Twist,
            input_topic,
            self.cmd_vel_callback,
            10
        )

        self.pub = self.create_publisher(
            TwistStamped,
            output_topic,
            10
        )

        self.get_logger().info(
            f'Bridge started: {input_topic} (Twist) -> {output_topic} (TwistStamped), frame_id={self.frame_id}'
        )

    def cmd_vel_callback(self, msg: Twist) -> None:
        out = TwistStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = self.frame_id
        out.twist = msg
        self.pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CmdVelToAckermannRef()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
