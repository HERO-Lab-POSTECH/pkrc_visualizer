# Changelog

## [0.1.0] — 2026-05-03 (Unreleased)

### Added
- 패키지 부트스트랩 (package.xml, setup.py, ament_python).
- `topic_config.py` — 토픽 → 페이지 매핑 (13개 토픽).
- `RosClient` — rclpy 별도 스레드 spin + `pyqtSignal` 브리지.
- `MainWindow` — 햄버거 ☰ 버튼 + `DrawerMenu` 슬라이드 + `QStackedWidget` 4페이지 라우팅.
- `BasePage` — show/hide 시 `QTimer` start/stop, 시그널 연결 헬퍼.
- `ImagePage` — Oculus M750D/M3000D, Ping360, Sonoptix 4탭 이미지 표시.
- `PosePage` — matplotlib XY 궤적 + Path 오버레이 + confidence 라벨.
- `SlamPage` — pyvistaqt 점군 viewer (`/fast_lio/cloud_registered_body`).
- `MappingPage` — 점군 + MarkerArray 오버레이 (`/sonar_3d_mapper/...`).
- `TopicHzStatusBar` — 1초 sliding window Hz 추정 표시.
- `test_ros_client.py`, `test_main_window.py` — 4개 테스트 PASS.

### Verification
- `colcon build --symlink-install --packages-select pkrc_visualizer` PASS.
- `xvfb-run -a pytest test/` PASS (4 tests).
- 수동 smoke: `ros2 run pkrc_visualizer pkrc_viz` → 4페이지 정상 동작 (헤드 환경 필요).

### Notes
- GitHub remote 연결·푸시는 사용자 명시 지시 시.
- 메타-리포(`pkrc-workspace/pkrc.repos`) 갱신은 별도 PR.
