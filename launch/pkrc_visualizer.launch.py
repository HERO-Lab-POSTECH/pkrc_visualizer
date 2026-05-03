"""pkrc_visualizer 단일 노드 실행."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        Node(
            package="pkrc_visualizer",
            executable="pkrc_viz",
            name="pkrc_visualizer",
            output="screen",
        ),
    ])
