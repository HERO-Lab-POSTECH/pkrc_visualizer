# Changelog

## [Unreleased] — Phase P4d: Topic rename (refactor)

### Changed
- `topic_config.py` — 8 TopicSpec subscriber topic_name 갱신 (spec §2.3):
  - `slam_cloud`: `/fast_lio/debug/cloud_registered` → `/fast_lio/debug/points_world`
  - `slam_path`: `/fast_lio/path` → `/fast_lio/debug/path`
  - `pose_odom`: `/fast_lio/odometry` → `/localization/fast_lio/odometry`
  - `pose_loc_odom`: `/fast_lio/localization/odometry` → `/localization/fast_lio_loc/odometry`
  - `pose_confidence`: `/fast_lio/localization/confidence` → `/localization/fast_lio_loc/confidence`
  - `pose_path`: `/fast_lio/path` → `/fast_lio/debug/path`
  - `map_cloud`: `/sonar_3d_mapper/point_cloud` → `/perception/sonar_3d/points`
  - `map_markers`: `/sonar_3d_mapper/marker_array` → `/perception/sonar_3d_visualizer/markers`
- `pages/slam_page.py` — docstring 토픽명 갱신 (`cloud_registered` → `points_world`).
- `pages/mapping_page.py` — docstring 토픽명 갱신 (`sonar_3d_mapper/...` → `perception/sonar_3d/...`).
- `README.md` — Pages 테이블 토픽명 갱신.

### Verification
- `colcon build --symlink-install --packages-select pkrc_visualizer` PASS (0.45s).
- static grep: legacy topic refs 0건 (`/fast_lio/odometry`, `/sonar_3d_mapper/*` 등).

### Notes
- Cross-repo dependency: lidar_slam P4b (PR #15) + sonar_3d_reconstruction P4c (PR #11) 이미 머지.
- P5 (Launch arg + ROS Time) 준비 완료.

## [0.5.0] — 2026-05-05 — rqt-style Image Page

### Removed
- `ImageLayoutSettings.layout` and `ImageLayoutSettings.splitter_state`
  fields. v0.4.0 yaml files keep their `panels` list; the two removed
  keys are silently dropped via `_filter_known`.
- `ImageToolbar` layout combobox + `layout_changed` signal +
  `set_layout_value`. Layout presets (`1x1` / `2x1` / `2x2` / `3x2` /
  `free`) no longer exist as a UI choice.
- `test/test_image_page_splitter.py` (replaced by
  `test/test_image_page_dock.py`).

### Added
- `ImageLayoutSettings.dock_state: str` — base64-encoded
  `QMainWindow.saveState()` capturing the full dock geometry (positions,
  splits, tabs, floating windows).
- `ImagePanelSettings.object_name: str` — stable `panel_<uuid>` id so
  `restoreState` re-attaches the same dock between sessions (otherwise
  every spawn would generate a fresh uuid and tabify/floating state
  would be lost on reload).
- `ImagePage` now hosts an inner `QMainWindow`. Each panel is a
  `QDockWidget(panel_<uuid4>)` with `Movable | Floatable | Closable`
  features. Users drag dock headers to relocate, tabify, or float —
  rqt parity.
- `ImagePanel.make_titlebar(close_cb)` factory returns a single-line
  `QWidget` (combobox + Hz label + ✕) that the dock installs as
  `setTitleBarWidget`. The panel body is purely the `ImageView`.
- `_DockCloseFilter(QObject)` event filter intercepts `QEvent.Close` so
  both the titlebar ✕ and programmatic `dock.close()` route through the
  same panel-removal path.
- `test/test_image_page_dock.py` — 7 tests covering default empty,
  add viewer, horizontal split, close → remove, dock_state roundtrip,
  tabify/float persistence, legacy yaml drop.
- `test/test_migration_v04_to_v05.py` — explicit v0.4.0 → v0.5.0 yaml
  migration coverage (legacy keys dropped on load + on subsequent save).

### Changed
- First-run UX: ImagePage is empty (no auto-spawned panels). Users
  click "+ Add Viewer" in the toolbar to create the first dock.
- `ImagePanel` no longer carries an inline header. Combobox / Hz /
  close live exclusively inside the dock title bar.
- `ImageToolbar` reduced to a single Add Viewer button +
  `add_viewer_clicked` signal.

### Fixed
- ImagePage panel ✕ button now actually removes the panel. The
  titlebar close button is wired to `dock.close()` so both the
  user-clicked path and the programmatic `dock.close()` path go
  through the same `QEvent.Close` filter, and the close-handler
  lambda is pinned to the dock so its lifetime survives PyQt5's
  weak-ref edge cases on `QPushButton.clicked.connect`.
- `cloud.size_unit` toggle no longer freezes the GPU. The clamp lives
  in two layers: `SettingsPanel` snaps the size slider visually when
  the user toggles the unit combobox, and `DisplaySettingsStore.update`
  re-applies the clamp atomically inside the same transaction so the
  view never receives a stale (size_unit, size) pair while the panel's
  two debounce timers are still settling. Prior to the store-layer
  guard, the size_unit signal usually beat the size signal to the view
  and `vtkPointGaussianMapper` briefly painted a 10 m splat that froze
  the GPU.
- `cloud.style` (`points` / `square` / `spheres`) now affects
  meters-mode splats. `vtkPointGaussianMapper` receives an explicit
  `SetSplatShaderCode` per style with a `discard` outside the unit
  disc/box, removing the "white square outline around a gaussian
  disc" artefact that appeared with the default splat shader.
  `SetTriangleScale(1.0)` is applied when the VTK build exposes it,
  so the visible splat radius equals `cloud.size` literally.

### Verification
- `python3 -m pytest test/ -q` PASS (96 tests, +12 from v0.4.0).
- `colcon build --symlink-install --packages-select pkrc_visualizer`
  PASS.
- Manual smoke on `7_ucrc_watertank/m3000d-range10-tilt90` bag pending
  (PR description tracks).

### Notes
- **One-time layout reset for v0.4.0 users.** When v0.5.0 first opens
  an existing `~/.config/pkrc_visualizer/display_settings.yaml`,
  panels are recreated in a default left-to-right horizontal row (the
  saved `splitter_state` is dropped). User drags to taste, then the
  new `dock_state` persists.
- `PyVistaView.__init__` (94 LOC) remains over the 50-LOC limit. This
  was flagged as a v0.4.0 cleanup follow-up and is unchanged by v0.5.0
  scope (ImagePage redesign). Defer to a dedicated PyVistaView
  refactor.
- Perspective save/load (multiple named layouts), cross-page docking,
  and "undo close" are deferred — see spec Out of Scope.

## [0.4.0] — 2026-05-04 — Cloud rendering & layout polish

### Added
- `CloudSettings.size_unit: "pixels" | "meters"` — meters mode swaps the
  cloud actor mapper to `vtkPointGaussianMapper(SetScaleFactor=size,
  EmissiveOff)` so splats render in world units and zoom with the camera.
- **Default `size_unit` is now `meters`** (was `pixels`) so first-run users
  immediately get zoom-aware splats. Existing YAML files keep their saved
  value via `_filter_known`.
- `cloud.size` slider widened to `min=0.01, max=20.0, step=0.1` (was
  `min=1.0, max=20.0, step=1.0`) so meters mode can express sub-meter
  splat radii (e.g. 0.05 m) without breaking pixel-mode usability.
- `ImageLayoutSettings.splitter_state: str` — serialized splitter sizes
  (`"outer_csv; row0_csv; row1_csv"`).
- `ImagePage` now builds `1x1` and `free` via `QGridLayout` and `2x1`,
  `2x2`, `3x2` via single or nested `QSplitter` so users can drag
  dividers to resize panels. State is preserved when layout id is
  unchanged and silently dropped on layout change.
- `pyvista_view.PyVistaView._install_point_mapper(actor, size_unit, size)`
  — idempotent mapper swap helper (vtkPolyDataMapper ↔
  vtkPointGaussianMapper).

### Changed
- `CloudSettings.decay_max_points: int = 300_000` →
  `decay_seconds: float = 30.0` (0.0 disables decay; RViz convention).
  Existing YAML entries with `decay_max_points` are silently dropped via
  `_filter_known` forward-compat.
- `PyVistaView._accum_points` (single ndarray FIFO) →
  `_accum_chunks: deque[(monotonic_ts, ndarray)]`.
  `HARD_MAX_ACCUM_POINTS = 2_000_000` is a runaway-producer backstop.
- Settings schema: `cloud.decay_max_points` (spinbox_int) →
  `cloud.decay_seconds` (spinbox_float, 0.0–600.0). New
  `cloud.size_unit` combobox (`pixels` | `meters`).
- `pyvista_view`: `import time` → `from time import monotonic` so tests
  can monkeypatch the clock without disturbing the global time module.
- `image_toolbar.set_layout_value` no longer suppresses
  `layout_changed` — `ImagePage._restore_from_store` uses an explicit
  disconnect/reconnect pattern instead.

### Verification
- `python3 -m pytest test/ -q` PASS (84 tests, +24 from v0.3.1).
- Manual on `7_ucrc_watertank` `m3000d-range10-tilt90` bag is required
  for full feature smoke (decay 0/5/30 s trail length, size_unit
  pixels↔meters zoom response, ImagePage divider drag + persistence).

### Notes
- TF integration (multi-publisher coordinate alignment) is deferred to
  v0.5.0 (separate spec).
- `free` layout still uses the grid fallback (drag-to-reorder is out of
  scope for v0.4.0).

## [0.3.1] — 2026-05-04 — UI polish (dark theme + i18n)

### Added
- App-wide Fusion style + dark `QPalette` in `app.py::_apply_dark_theme` so
  every widget without an explicit stylesheet gets readable contrast.
- Cloud style `square` in `settings_schema.cloud_schema` and `pyvista_view`
  (`SetPointSmoothing(False)` for crisp GL_POINTS squares).

### Changed
- `SettingsButton` now anchors to bottom-right (was bottom-left); panel
  also right-aligns to the button's right edge.
- `SettingsPanel` stylesheet expanded so `QFormLayout` labels and inactive
  `QTabBar` tabs are visible against the dark background.
- `_ColorButton` chooses `#000` vs `#fff` text color from the BT.601 luma
  of the swatch (was hardcoded white, unreadable on light colors).
- All Korean docstrings / comments / placeholders / error strings replaced
  with ASCII English (broken-glyph-free in containers without Korean fonts).
  Affected: 13 source files + 8 test files.

### Verification
- `python3 -m pytest test/ -q` PASS (60/60).
- Manual: 7_ucrc_watertank `m3000d-range10-tilt90` bag replay — image
  page panels, settings overlay (frames/cloud/background tabs), label
  contrast, color picker swatch — all readable.

### Notes
- Resizable / draggable image panels (RQt-style), zoom-aware point size
  (world-units), and decay-by-time (RViz convention) are deferred to
  v0.4.0.

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
