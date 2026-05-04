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
| Sonar Image | 사용자 입력 (런타임) — `+ Add Viewer` 후 ROS 활성 토픽 중 `sensor_msgs/Image` 또는 `CompressedImage` 선택 |

토픽 매핑은 `pkrc_visualizer/topic_config.py`에서 변경.

## Display Properties (v0.2.0)

SLAM 및 Sonar Mapping 페이지의 3D 뷰포트 좌측 하단에 ⚙ 버튼이 표시됩니다.
클릭하면 Display Properties 패널이 열리며 다음 항목을 실시간으로 조정 가능:

- **Frames** — `map`/`base_link` triad의 표시 여부, 길이, 라인 굵기, 라벨 폰트
  크기, 라벨 색상.
- **Cloud** — point size, alpha, 표시 방식(points / spheres),
  color transformer (Flat / Z-축 jet), SLAM 한정 FIFO 누적 점수.
- **Background** — 뷰어 배경 색상.

설정은 변경 시 `~/.config/pkrc_visualizer/display_settings.yaml`에 자동 저장되고
재시작 시 복원됩니다. "Reset this tab to defaults" 버튼은 현재 탭만 초기화.

## Image Page Workflow (v0.3.0)

`Sonar Image` 페이지는 더 이상 고정 탭을 사용하지 않습니다. 사용자가
런타임에 직접 토픽을 추가:

1. 상단 `+ Add Viewer` 클릭 → 빈 패널 추가.
2. 패널의 콤보에 토픽 이름 일부 입력 → ROS에 활성 중인
   `sensor_msgs/Image` / `CompressedImage` 토픽 자동완성.
3. 선택 시 즉시 영상 표시. 패널 우상단 `✕`로 제거.

Layout 콤보로 그리드 모드 변경 (1×1 / 2×1 / 2×2 / 3×2 / free).
모든 패널 + layout 선택은 `~/.config/pkrc_visualizer/display_settings.yaml`에
자동 저장되어 재실행 시 복원.

## Cloud Rendering & Layout (v0.4.0)

- **v0.4.0** — Time-based cloud decay (RViz convention), zoom-aware
  point size (world units via `vtkPointGaussianMapper`), and
  resizable image panels (single or nested `QSplitter`).

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
