"""Launch the single pkrc_visualizer node."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    use_sim_time = LaunchConfiguration("use_sim_time")
    return LaunchDescription([
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="false",
            description=(
                "Honor /clock during bag replay. Required for stamps on "
                "/initialpose and any time-sensitive plot to align with "
                "bag clock instead of wall clock."
            ),
        ),
        Node(
            package="pkrc_visualizer",
            executable="pkrc_viz",
            name="pkrc_visualizer",
            output="screen",
            parameters=[{
                "use_sim_time": PythonExpression([
                    "'", use_sim_time, "' == 'true'",
                ]),
            }],
        ),
    ])
