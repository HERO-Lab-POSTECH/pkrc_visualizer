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

- 단일 프로세스 — Qt 메인 스레드(UI) + rclpy 별도 스레드(spin) + `pyqtSignal` queued connection.
- 활성 페이지만 10 Hz `QTimer`로 렌더 (비활성 페이지는 timer stop).
- 모든 토픽은 시작 시 한꺼번에 구독, 페이지 전환은 즉시.

설계 문서: `/workspace/docs/superpowers/specs/2026-05-03-pkrc-visualizer-design.md`

## Test

```bash
cd /workspace/ros2_ws/src/pkrc_visualizer
xvfb-run -a python3 -m pytest test/ -v
```

(헤드리스 환경에서는 PyVistaView OpenGL 컨텍스트 위해 xvfb-run 필요)

## Known limitations

- 점군 100k 이상에서 frame rate 저하 가능 — 다운샘플 미구현.
- Sonoptix 토픽 이름은 운용 환경마다 다름 → `pkrc_visualizer/topic_config.py`에서 수정.
- LaserScan(Ping360) 표시는 prototype에서 polar 미사용 (이미지 탭만).
- 메시지가 한 번도 안 들어온 토픽은 status bar에 라벨이 안 만들어짐 (실제 발행 시점부터 표시 시작).
