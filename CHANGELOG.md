# Changelog

## [0.3.0] — 2026-05-04 — Image Page Redesign

### Added
- `widgets/topic_combobox.py` — prefix 자동완성 콤보 (rqt_image_view 스타일).
- `widgets/image_panel.py` — 단일 패널 (콤보 + ImageView + Hz 라벨 + 닫기).
- `widgets/image_toolbar.py` — Add Viewer + Layout 콤보 (1×1/2×1/2×2/3×2/free).
- `RosClient.enable_discovery(msg_types)` + `topics_changed` 시그널 — 1Hz 폴링.
- `RosClient.subscribe_dynamic(topic_name, msg_type)` / `unsubscribe(topic_id)` —
  ref-counted 동적 구독.
- `display_settings.py`: `ImagePanelSettings` + `ImageLayoutSettings`,
  `PageDisplaySettings.image` 필드.
- `ImageView`가 `sensor_msgs/CompressedImage`를 cv2.imdecode 경로로 처리.

### Changed
- `pages/image_page.py` 전면 재작성 — 4개 하드코딩 탭 → 동적 패널 그리드.
- `topic_config.py`의 `TOPICS["image"]` 제거. 사용자가 런타임에 토픽 입력.
- `MainWindow`가 `ImagePage`에도 `DisplaySettingsStore` 주입.

### Verification
- `python3 -m pytest test/ -v` PASS (60 tests, +22 from 0.2.0).

### Notes
- LaserScan polar 표시 (Ping360 등)는 별도 Spec C로 deferred.
- Free 레이아웃의 드래그 위치는 세션 단위 휘발성. layout=free 모드 자체는 영구 저장.
- `image_transport` 플러그인(theora, h264 등)은 후속 spec — v0.3.0은
  raw `Image` + `CompressedImage`만 지원.

## [0.2.0] — 2026-05-04 — Display Properties

### Added
- `display_settings.py` — 페이지별 dataclass + YAML codec
  (`~/.config/pkrc_visualizer/display_settings.yaml`). 손상된 YAML은 `*.bak`으로
  rename 후 기본값으로 폴백.
- `widgets/settings_panel.py` — schema-driven 탭 폼 (Frames / Cloud / Background),
  200 ms 디바운스 필드 시그널 + Reset-this-tab 버튼.
- `widgets/settings_schema.py` — 탭별 `FieldSpec` 선언 리스트.
- `widgets/settings_button.py` — 좌측 하단 ⚙ 오버레이 버튼
  (VTK 캔버스 위에 z-order 보장 위해 `WA_NativeWindow` 사용).
- `PyVistaView.apply_display_settings()` + Z-축 컬러용 jet LUT.

### Changed
- `MainWindow.__init__`이 `DisplaySettingsStore`를 받도록 변경. `app.main`이
  프로세스당 하나의 store를 생성해 MainWindow에 주입.
- `SlamPage`/`MappingPage` 생성자도 store를 받아 PyVistaView에 설정 패널 설치
  (SLAM `include_decay=True`, Mapping `False` — Mapping은 누적이 아니므로
  FIFO 길이 옵션 숨김).
- `PyVistaView.MAX_ACCUM_POINTS` (클래스 상수) → `self.max_accum_points`
  (인스턴스 속성)로 전환 — 런타임에 FIFO 길이 변경 가능.

### Verification
- `python3 -m pytest test/ -v` PASS (37 tests, +24 from 0.1.0).
- 통합 테스트(`test_settings_integration.py`) — store ↔ panel ↔ view round-trip
  + reset 동작 검증.

### Notes
- `Color transformer = intensity` 옵션은 스키마에 있으나 현재 flat 경로로 매핑됨
  (PointCloud2 intensity 필드 plumbing은 후속 spec에서 처리).
- Display Properties는 SLAM·Sonar Mapping 페이지에만 적용. Pose / Image 페이지는
  변경 없음 (Image 페이지 재설계는 Spec B로 별도 진행).

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
