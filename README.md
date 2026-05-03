# pkrc_visualizer

PKRC 수중 3D 재구성 프로젝트의 통합 시각화 도구. 햄버거 메뉴로 4개 페이지(SLAM · 위치 · Sonar Mapping · Sonar Image)를 라우팅하는 단일 PyQt5 윈도우 ROS2 노드.

## Install

```bash
# pip 의존성 (1회)
pip install --user -r requirements.txt

# colcon 빌드
cd /workspace/ros2_ws
colcon build --symlink-install --packages-select pkrc_visualizer
source install/setup.bash
```

## Run

```bash
ros2 launch pkrc_visualizer pkrc_visualizer.launch.py
# 또는
ros2 run pkrc_visualizer pkrc_viz
```

## Pages

| 메뉴 | 토픽 |
|---|---|
| SLAM | `/fast_lio/cloud_registered_body`, `/fast_lio/path` |
| 위치/경로 | `/fast_lio/odometry`, `/fast_lio/localization/{odometry, confidence}`, `/fast_lio/path` |
| Sonar Mapping | `/sonar_3d_mapper/point_cloud`, `/sonar_3d_mapper/marker_array` |
| Sonar Image | Oculus(`/sensor/sonar/oculus/.../image`), Ping360(`.../image`, `.../scan`), Sonoptix(`.../`) |

토픽 매핑은 `pkrc_visualizer/topic_config.py`에서 변경.

## Architecture

설계 문서: `/workspace/docs/superpowers/specs/2026-05-03-pkrc-visualizer-design.md`
