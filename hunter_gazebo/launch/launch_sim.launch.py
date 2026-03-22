import os

from launch_ros.actions import Node

from launch import LaunchDescription
from launch.event_handlers import OnProcessExit

from launch.conditions import IfCondition

from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue

from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution, LaunchConfiguration
from launch.actions import ExecuteProcess, IncludeLaunchDescription, RegisterEventHandler, DeclareLaunchArgument

from ament_index_python.packages import get_package_share_directory

from typing import Final

import xacro

PKG_HUNTER_DESCRIPTION: Final = 'hunter_description'
PKG_HUNTER_GAZEBO: Final = 'hunter_gazebo'
JOINT_STATE_BROADCASTER_CONTROLLER: Final = 'joint_state_broadcaster'
ACKERMANN_LIKE_CONTROLLER: Final = 'ackermann_like_controller'


def generate_launch_description():

    # Declare Arguments
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument(
            'gui',
            default_value='true',
            description="Start RViz2 automatically with this launch file."
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        )
    )
    # Initialize Arguments
    gui_arg = LaunchConfiguration('gui')
    use_sim_time_arg = LaunchConfiguration('use_sim_time')

    # Package Directories
    pkg_hunter_description = get_package_share_directory(PKG_HUNTER_DESCRIPTION)
    pkg_hunter_gazebo = get_package_share_directory(PKG_HUNTER_GAZEBO)
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    # Declare the use_sim_time argument
    use_sim_time = {'use_sim_time': use_sim_time_arg}

    # Parse URDF via xacro
    robot_description_file = os.path.join(pkg_hunter_description, 'description', 'robot.urdf.xacro')
    robot_description = {"robot_description": xacro.process_file(robot_description_file).toxml()}

    ros_gz_bridge_config = os.path.join(pkg_hunter_gazebo, 'config', 'ros_gz_bridge.yaml')

    ros2_control_config_file = os.path.join(pkg_hunter_description, 'config', 'ackermann_like_controller.yaml')
    rviz_config_file = os.path.join(pkg_hunter_description, 'rviz', 'robot_view.rviz')    

    # Start gz sim
    gz_sim_ndoe = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            'gz_args': '-r empty.sdf'
        }.items(),
    )

    # Spawn Robot in Gz sim
    spawn_node = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-topic', '/robot_description', 
            '-name', 'hunter',
            "-z", "1.5",
            "-x", "0.0",
            "-y", "0.0"
        ],
        output='screen'
    )

    # Bridge ROS topics and Gz message for establishing communication
    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",  # 负责把 ROS 2 topic 和 Gazebo Transport topic 连起来
        parameters=[{
            'config_file': ros_gz_bridge_config
        }],
        output="screen",
    )
    
    # Start robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='both',
        parameters=[
            robot_description,
            use_sim_time,
        ],
    )

    # 解析时 GazeboSimROS2ControlPlugin 会直接生成 Controller Manager，在此不再重复声明。

    # 拉起 joint_state_broadcaster Controller
    joint_state_broadcaster_spanwer_node = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            JOINT_STATE_BROADCASTER_CONTROLLER,
            '--controller-manager', '/controller_manager',
            '--param-file', ros2_control_config_file,
        ]
    )
    # 拉起 ackermann_like_controller Controller
    ackermann_like_controller_spawner_node = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            ACKERMANN_LIKE_CONTROLLER,
            '--controller-manager', '/controller_manager',
            '--param-file', ros2_control_config_file,
            '--controller-ros-args', '-r /ackermann_like_controller/tf_odometry:=/tf',    
        ],
    )
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config_file,],
        output='screen',
        parameters=[use_sim_time],
        condition=IfCondition(gui_arg)
    )
    # 1) joint_state_broadcaster 结束后，启动 ackermann controller spawner
    delay_ackermann_after_joint_state_broadcaster_spawner_node = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spanwer_node,
            on_exit=[ackermann_like_controller_spawner_node],
        )
    )
    # 2) ackermann controller spawner 结束后，再启动 RViz
    delay_rviz_after_ackermann_controller_spawner_node = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=ackermann_like_controller_spawner_node,
            on_exit=[rviz_node],
        )
    )

    # Launch the rqt_joint_trajectory_controller standalone
    rqt_robot_steering = ExecuteProcess(
            cmd=['rqt', '--standalone', 'rqt_robot_steering'],
            output='screen',
    )

    nodes = [
        # Gz Sim 侧
        gz_sim_ndoe,
        spawn_node,
        ros_gz_bridge,

        # ROS2 侧
        robot_state_publisher,
        joint_state_broadcaster_spanwer_node,
        delay_ackermann_after_joint_state_broadcaster_spawner_node,
        delay_rviz_after_ackermann_controller_spawner_node,

        rqt_robot_steering
    ]

    return LaunchDescription(declared_arguments + nodes)
