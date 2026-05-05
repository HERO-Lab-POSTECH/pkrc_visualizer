"""Launch the single pkrc_visualizer node."""
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
