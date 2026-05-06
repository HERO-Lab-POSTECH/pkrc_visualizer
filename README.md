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
| SLAM | `/fast_lio/debug/points_world`, `/fast_lio/debug/path`, `/localization/fast_lio_loc/occupancy_grid` (transient_local, 선택) |
| 위치/경로 | `/localization/fast_lio/odometry`, `/localization/fast_lio_loc/{odometry, confidence}`, `/fast_lio/debug/path` |
| Sonar Mapping | `/perception/sonar_3d/points`, `/perception/sonar_3d_visualizer/markers` |
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

## SLAM Prior Map + Pose Estimate (v0.6.0)

`fast-lio` localization 모드에서 SLAM 페이지가 prior PCD를 z 슬라이스로 변환한
2D OccupancyGrid (`/localization/fast_lio_loc/occupancy_grid`)를 자동 구독하여
`map` frame의 z=0 평면에 텍스처로 렌더링한다. 누적 LiDAR 스캔이 그 평면 위에
겹쳐 보인다.

설정 패널 SLAM 탭의 **Prior Map** 그룹에서 표시 on/off와 alpha를 조절할 수 있다.

페이지 좌상단의 **Pose Estimate** 토글을 누르면 RViz의 "2D Pose Estimate"와 동등한
입력 모드가 활성화된다:

1. 카메라가 자동으로 top-down으로 전환 (이전 시점 저장).
2. 평면 위에서 좌클릭 + 드래그하면 임시 화살표가 그려지고, release 시
   (시작점 = position, 드래그 방향 = yaw)이 `/initialpose`로 publish된다.
3. 토글을 다시 누르면 직전 카메라 시점으로 복귀.

`fast-lio`의 `localization_node`가 이미 `/initialpose`를 구독 중이므로 RViz
없이도 단독으로 초기 위치 입력이 가능하다.

## Image Page Workflow (v0.5.0 — rqt-style)

`Sonar Image` 페이지는 자유 배치 dock 영역입니다. 고정 layout 모드
(1×1 / 2×1 / 2×2 / 3×2 / free)는 더 이상 존재하지 않습니다.

1. 상단 `+ Add Viewer` 클릭 → 빈 dock 패널 추가.
2. 패널 헤더의 콤보에 토픽 이름 일부 입력 → ROS에 활성 중인
   `sensor_msgs/Image` / `CompressedImage` 토픽 자동완성.
3. 패널 헤더(combobox + Hz + ✕)를 **드래그**하여 자유 배치:
   - 다른 패널의 가장자리에 떨어뜨리면 좌/우/위/아래 split.
   - 다른 패널의 헤더에 떨어뜨리면 tab으로 묶임 (tabify).
   - 도크 영역 밖으로 끌어내면 floating window로 분리.
4. 헤더 우측 ✕ 버튼으로 제거.

도크 위치/크기/탭/플로팅 상태는 모두
`~/.config/pkrc_visualizer/display_settings.yaml`의 `dock_state` 필드
(base64 `QMainWindow.saveState`)에 자동 저장되어 재실행 시 복원됩니다.
v0.4.0 이전 yaml은 `panels` 리스트만 살리고 layout 정보는 자연 무시 →
첫 v0.5.0 실행 시 가로 1열로 재배치됩니다.

## Cloud Rendering (v0.4.0)

- Time-based cloud decay (RViz convention), zoom-aware point size
  (world units via `vtkPointGaussianMapper`).

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
