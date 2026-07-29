# Cloud size per unit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pkrc_visualizer`의 cloud point/splat 사이즈를 단위(pixels/meters)별로 분리 저장하여, 단위 토글 시 무손실로 동작하고 GPU 멈춤 가드 코드를 모두 제거한다.

**Architecture:** `CloudSettings`에 `size_pixels`/`size_meters`를 두고 `active_size` 프로퍼티로 렌더가 활성 단위를 라우팅. 설정 패널은 `cloud.size_unit`이 바뀌면 cloud 탭을 부분 재빌드하여 단위별 슬라이더(path/range/label/step)가 갈아끼워짐. 기존 yaml의 단일 `cloud.size`는 활성 단위 쪽으로 자동 마이그레이션.

**Tech Stack:** Python 3.10, PyQt5, dataclasses, PyYAML, pytest, VTK 9.x (vtkPointGaussianMapper / vtkPolyDataMapper).

**Spec:** `docs/superpowers/specs/2026-05-07-cloud-size-per-unit-design.md`

**Target version:** `0.7.0` → `0.8.0` (minor bump, schema 변경)

---

## File Structure

### Modified files

- `pkrc_visualizer/display_settings.py` — `CloudSettings` 필드 추가/제거, `active_size` 프로퍼티, `settings_from_dict` 마이그레이션, `DisplaySettingsStore.update`에서 가드 hook 제거, 가드 함수/상수 삭제.
- `pkrc_visualizer/widgets/settings_schema.py` — `cloud_schema(include_decay, size_unit)` 시그니처 + 단위별 동적 FieldSpec, `panel_tabs(...)` 시그니처에 `size_unit` 추가.
- `pkrc_visualizer/widgets/settings_panel.py` — `_guard_size_on_unit_change` + 상수 제거, `rebuild_cloud_tab(size_unit)` 메서드 추가, 콤보 hook을 rebuild 트리거로 교체.
- `pkrc_visualizer/widgets/pyvista_view.py` — `_apply_cloud`의 `c.size` → `c.active_size`.
- `pkrc_visualizer/pages/base_page.py` — `panel_tabs` 호출 시 현재 페이지의 `cloud.size_unit` 전달, store changed 핸들러에서 size_unit 변경 감지 시 `panel.rebuild_cloud_tab()` 호출.
- `package.xml`, `setup.py` — `0.7.0` → `0.8.0`.
- `CHANGELOG.md` — `## [0.8.0]` 블록 추가.
- `README.md` — Settings 섹션 한 단락 갱신.

### Modified test files

- `test/test_display_settings.py` — 새 필드 defaults/active_size/migration 테스트 추가; clamp 테스트 3개 제거; `cloud.size`를 직접 참조하던 기존 테스트들의 필드 참조 갱신.
- `test/test_settings_panel.py` — clamp 테스트 3개 제거; lossless toggle 및 슬라이더 swap 테스트 추가; 기존 통계 카운트(`frames(9) + cloud(9 …)`) 검증 갱신.
- `test/test_settings_integration.py` — 슬라이더 path를 단위별 경로로 갱신.
- `test/test_pyvista_size_unit.py` — `_apply` 헬퍼의 `s.cloud.size = ...`를 `size_pixels`/`size_meters`로 분기.
- `test/test_pyvista_apply_settings.py` — `active_size` 라우팅 테스트 추가.

### No-touch files

페이지 자체(`slam_page.py`, `mapping_page.py`, `pose_page.py`, `image_page.py`)는 schema-driven hookup 덕분에 변경 없음.

---

## Task 1: 새 필드 + `active_size` 프로퍼티 + 단위별 yaml round-trip

레거시 `size` 필드는 **남겨둔다** (다음 task들이 점진 전환을 마칠 때까지 무해). 이 task는 데이터 모델 확장만 다룬다.

**Files:**
- Modify: `pkrc_visualizer/display_settings.py:29-39` (`CloudSettings` 클래스)
- Test: `test/test_display_settings.py` (additive only)

- [ ] **Step 1: 실패하는 테스트 4개 추가**

`test/test_display_settings.py` 파일 끝에 추가:

```python
def test_cloud_size_per_unit_defaults():
    s = CloudSettings()
    assert s.size_pixels == 1.0
    assert s.size_meters == 0.01


def test_active_size_routes_to_meters_when_unit_meters():
    s = CloudSettings(size_unit="meters", size_pixels=5.0, size_meters=0.03)
    assert s.active_size == 0.03


def test_active_size_routes_to_pixels_when_unit_pixels():
    s = CloudSettings(size_unit="pixels", size_pixels=5.0, size_meters=0.03)
    assert s.active_size == 5.0


def test_cloud_size_per_unit_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "slam": PageDisplaySettings(
            cloud=CloudSettings(
                size_unit="pixels", size_pixels=7.0, size_meters=0.04,
            ),
        ),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["slam"].cloud.size_pixels == 7.0
    assert loaded["slam"].cloud.size_meters == 0.04
    assert loaded["slam"].cloud.size_unit == "pixels"
```

- [ ] **Step 2: 테스트 실행 — 4개 모두 실패해야 함**

```
cd /home/hero/ros2_ws/src/pkrc_visualizer
python -m pytest test/test_display_settings.py::test_cloud_size_per_unit_defaults \
  test/test_display_settings.py::test_active_size_routes_to_meters_when_unit_meters \
  test/test_display_settings.py::test_active_size_routes_to_pixels_when_unit_pixels \
  test/test_display_settings.py::test_cloud_size_per_unit_yaml_roundtrip -v
```
Expected: 4 FAILED — `AttributeError: 'CloudSettings' object has no attribute 'size_pixels'` (또는 동일).

- [ ] **Step 3: `CloudSettings`에 새 필드 + 프로퍼티 추가**

`pkrc_visualizer/display_settings.py:29-39`의 `CloudSettings`를 다음으로 교체:

```python
@dataclass
class CloudSettings:
    style: str = "points"            # points | square | spheres
    size: float = 2.0                # legacy (Task 3에서 제거)
    size_pixels: float = 1.0         # px 모드 사이즈
    size_meters: float = 0.01        # meter 모드 사이즈
    size_unit: str = "meters"        # pixels | meters
    alpha: float = 1.0
    decay_seconds: float = 30.0      # 0.0 disables decay (accumulate forever, capped by HARD_MAX)
    color_transformer: str = "flat"  # flat | z | intensity
    flat_color: str = "#4fc3f7"
    color_min: float = 0.0
    color_max: float = 10.0

    @property
    def active_size(self) -> float:
        return self.size_meters if self.size_unit == "meters" else self.size_pixels
```

- [ ] **Step 4: 테스트 실행 — 4개 모두 통과해야 함**

```
python -m pytest test/test_display_settings.py::test_cloud_size_per_unit_defaults \
  test/test_display_settings.py::test_active_size_routes_to_meters_when_unit_meters \
  test/test_display_settings.py::test_active_size_routes_to_pixels_when_unit_pixels \
  test/test_display_settings.py::test_cloud_size_per_unit_yaml_roundtrip -v
```
Expected: 4 PASSED.

- [ ] **Step 5: 전체 회귀 — 기존 테스트들 무영향 확인**

```
python -m pytest test/test_display_settings.py -v
```
Expected: 모두 PASS (legacy `size` 필드가 그대로 있으므로 기존 테스트 영향 없음).

- [ ] **Step 6: 커밋**

```
cd /home/hero/ros2_ws/src/pkrc_visualizer
git add pkrc_visualizer/display_settings.py test/test_display_settings.py
git commit -m "feat(display-settings): add per-unit cloud size fields and active_size property

- CloudSettings.size_pixels (default 1.0), size_meters (default 0.01)
- active_size property routes by size_unit
- legacy size field retained for incremental transition"
```

---

## Task 2: legacy `cloud.size` → 새 필드 yaml 마이그레이션

`settings_from_dict`에서 legacy 단일 `size`를 활성 단위 쪽 새 필드로 in-place 이전. 다른 단위는 dataclass 기본값으로 채워짐. 신/구 키가 모두 있으면 새 키 우선.

**Files:**
- Modify: `pkrc_visualizer/display_settings.py:90-117` (`settings_from_dict`)
- Test: `test/test_display_settings.py` (additive)

- [ ] **Step 1: 실패하는 테스트 3개 추가**

`test/test_display_settings.py` 파일 끝에 추가:

```python
def test_cloud_size_legacy_migration_meters():
    """legacy {size: 4.0, size_unit: meters} → size_meters=4.0, size_pixels=default(1.0)."""
    s = settings_from_dict({"cloud": {"size": 4.0, "size_unit": "meters"}})
    assert s.cloud.size_meters == 4.0
    assert s.cloud.size_pixels == 1.0      # default
    assert s.cloud.size_unit == "meters"


def test_cloud_size_legacy_migration_pixels():
    """legacy {size: 8.0, size_unit: pixels} → size_pixels=8.0, size_meters=default(0.01)."""
    s = settings_from_dict({"cloud": {"size": 8.0, "size_unit": "pixels"}})
    assert s.cloud.size_pixels == 8.0
    assert s.cloud.size_meters == 0.01     # default
    assert s.cloud.size_unit == "pixels"


def test_cloud_size_legacy_ignored_when_new_present():
    """신/구 키가 모두 있으면 새 키 우선, legacy size는 무시."""
    s = settings_from_dict({"cloud": {
        "size": 99.0,
        "size_pixels": 3.0,
        "size_meters": 0.02,
        "size_unit": "pixels",
    }})
    assert s.cloud.size_pixels == 3.0
    assert s.cloud.size_meters == 0.02
```

- [ ] **Step 2: 테스트 실행 — 3개 모두 실패해야 함**

```
python -m pytest test/test_display_settings.py::test_cloud_size_legacy_migration_meters \
  test/test_display_settings.py::test_cloud_size_legacy_migration_pixels \
  test/test_display_settings.py::test_cloud_size_legacy_ignored_when_new_present -v
```
Expected: 3 FAILED. legacy `size`는 `_filter_known`이 알기 때문에 그대로 `cloud.size`에 들어가고, 새 필드는 default라 assertion 실패.

- [ ] **Step 3: `settings_from_dict`에 마이그레이션 분기 추가**

`pkrc_visualizer/display_settings.py:90-117`의 `settings_from_dict`를 다음으로 교체:

```python
def settings_from_dict(d: dict[str, Any]) -> PageDisplaySettings:
    frames = FramesSettings(**_filter_known(FramesSettings, d.get("frames", {})))

    cloud_raw = d.get("cloud", {})
    if not isinstance(cloud_raw, dict):
        cloud_raw = {}
    # Legacy migration: pre-0.8 had a single `size` field whose meaning
    # depended on `size_unit`. Map it to whichever side of the new split
    # was active; leave the other side at its default. New keys win if
    # both are present.
    if (
        "size" in cloud_raw
        and "size_pixels" not in cloud_raw
        and "size_meters" not in cloud_raw
    ):
        legacy_size = cloud_raw.pop("size")
        unit = cloud_raw.get("size_unit", _DEFAULTS.cloud.size_unit)
        if unit == "meters":
            cloud_raw["size_meters"] = legacy_size
        else:
            cloud_raw["size_pixels"] = legacy_size
    cloud = CloudSettings(**_filter_known(CloudSettings, cloud_raw))

    prior_map = PriorMapSettings(
        **_filter_known(PriorMapSettings, d.get("prior_map", {})))
    image_dict = d.get("image", {})
    if not isinstance(image_dict, dict):
        image_dict = {}
    raw_panels = image_dict.get("panels", [])
    panels = [
        ImagePanelSettings(**_filter_known(ImagePanelSettings, p))
        for p in raw_panels if isinstance(p, dict)
    ]
    image = ImageLayoutSettings(
        **{
            **_filter_known(ImageLayoutSettings, image_dict),
            "panels": panels,
        }
    )
    return PageDisplaySettings(
        background=d.get("background", _DEFAULTS.background),
        frames=frames,
        cloud=cloud,
        prior_map=prior_map,
        image=image,
    )
```

- [ ] **Step 4: 테스트 실행 — 3개 모두 통과해야 함**

```
python -m pytest test/test_display_settings.py::test_cloud_size_legacy_migration_meters \
  test/test_display_settings.py::test_cloud_size_legacy_migration_pixels \
  test/test_display_settings.py::test_cloud_size_legacy_ignored_when_new_present -v
```
Expected: 3 PASSED.

- [ ] **Step 5: 전체 회귀 — 기존 테스트들 영향 없음 확인**

```
python -m pytest test/test_display_settings.py -v
```
Expected: 모두 PASS. (legacy `size` 필드 + 마이그레이션이 공존하므로 기존 테스트 영향 없음.)

- [ ] **Step 6: 커밋**

```
git add pkrc_visualizer/display_settings.py test/test_display_settings.py
git commit -m "feat(display-settings): migrate legacy cloud.size to per-unit fields on yaml load

- in-place migration in settings_from_dict
- legacy size copies into active unit's new field; other unit gets default
- new keys take precedence when both present"
```

---

## Task 3: 스위치오버 — 렌더 경로/스키마/패널 재빌드/가드 제거/legacy 필드 제거

이 task는 단일 커밋으로 일관성 있게 전환한다. 중간 상태(렌더는 active_size, UI는 legacy size)가 사용자에게 노출되지 않도록 하기 위함.

**Files:**
- Modify: `pkrc_visualizer/display_settings.py` (legacy `size` 제거, 가드 함수/상수/hook 제거)
- Modify: `pkrc_visualizer/widgets/settings_schema.py` (`cloud_schema` 시그니처 + 동적 필드, `panel_tabs` 시그니처)
- Modify: `pkrc_visualizer/widgets/settings_panel.py` (가드 제거, `rebuild_cloud_tab` 추가, 콤보 hook 교체)
- Modify: `pkrc_visualizer/widgets/pyvista_view.py` (`_apply_cloud`에서 `c.size` → `c.active_size`)
- Modify: `pkrc_visualizer/pages/base_page.py` (`panel_tabs`에 `size_unit` 전달, store changed 시 size_unit 변경 감지 → `rebuild_cloud_tab`)
- Modify tests: `test/test_display_settings.py`, `test/test_settings_panel.py`, `test/test_settings_integration.py`, `test/test_pyvista_size_unit.py`, `test/test_pyvista_apply_settings.py`

- [ ] **Step 1: 새 동작에 대한 실패 테스트 추가**

`test/test_settings_panel.py` 파일 끝에 다음을 추가 (기존 import는 그대로):

```python
def test_size_unit_toggle_swaps_active_slider(qtbot):
    from pkrc_visualizer.widgets.settings_schema import panel_tabs
    panel = SettingsPanel(panel_tabs(include_decay=True, size_unit="pixels"))
    qtbot.addWidget(panel)
    # 처음에는 pixels 슬라이더가 노출
    assert "cloud.size_pixels" in panel._widgets
    assert "cloud.size_meters" not in panel._widgets
    # meters로 전환
    panel.rebuild_cloud_tab("meters")
    assert "cloud.size_meters" in panel._widgets
    assert "cloud.size_pixels" not in panel._widgets


def test_size_unit_toggle_is_lossless(qtbot):
    """px=10 설정 → meters 전환 → pixels 복귀 시 슬라이더 값 10 유지."""
    from pkrc_visualizer.widgets.settings_schema import panel_tabs
    panel = SettingsPanel(panel_tabs(include_decay=True, size_unit="pixels"))
    qtbot.addWidget(panel)
    panel._widgets["cloud.size_pixels"].setValue(10.0)
    # 시뮬: page에 값 반영
    page = PageDisplaySettings()
    page.cloud.size_pixels = 10.0
    page.cloud.size_unit = "meters"
    panel.rebuild_cloud_tab("meters")
    panel.apply_values(page)
    assert panel._widgets["cloud.size_meters"].value() == page.cloud.size_meters  # default 0.01
    page.cloud.size_unit = "pixels"
    panel.rebuild_cloud_tab("pixels")
    panel.apply_values(page)
    assert panel._widgets["cloud.size_pixels"].value() == 10.0
```

`test/test_pyvista_apply_settings.py` 파일을 열어 (기존 import 활용) 끝에 다음 추가:

```python
def test_active_size_routes_per_unit_to_mapper(qtbot):
    """meters: SetScaleFactor=size_meters, pixels: SetPointSize=size_pixels."""
    import vtk
    from pkrc_visualizer.display_settings import PageDisplaySettings
    from pkrc_visualizer.widgets.pyvista_view import PyVistaView
    view = PyVistaView()
    qtbot.addWidget(view)

    s = PageDisplaySettings()
    s.cloud.size_unit = "meters"
    s.cloud.size_meters = 0.07
    s.cloud.size_pixels = 9.0
    view.apply_display_settings(s)
    assert isinstance(view._cloud_actor.GetMapper(), vtk.vtkPointGaussianMapper)
    assert view._cloud_actor.GetMapper().GetScaleFactor() == 0.07

    s.cloud.size_unit = "pixels"
    view.apply_display_settings(s)
    assert view._cloud_actor.GetProperty().GetPointSize() == 9.0
```

- [ ] **Step 2: 새 테스트가 실패하는지 확인 (구현 전)**

```
python -m pytest test/test_settings_panel.py::test_size_unit_toggle_swaps_active_slider \
  test/test_settings_panel.py::test_size_unit_toggle_is_lossless \
  test/test_pyvista_apply_settings.py::test_active_size_routes_per_unit_to_mapper -v
```
Expected: 3 FAILED — `panel_tabs() got unexpected keyword argument 'size_unit'` 또는 `'SettingsPanel' object has no attribute 'rebuild_cloud_tab'` 또는 `cloud.size_pixels not in panel._widgets`.

- [ ] **Step 3: `settings_schema.py` 동적 필드 + 시그니처 변경**

`pkrc_visualizer/widgets/settings_schema.py:36-87` 전체를 다음으로 교체 (기존 `cloud_schema`와 `panel_tabs` 함수 본문):

```python
def cloud_schema(include_decay: bool, size_unit: str) -> list[FieldSpec]:
    if size_unit == "meters":
        size_field = FieldSpec(
            "cloud.size_meters", "Size (m)", "slider",
            {"min": 0.001, "max": 0.5, "step": 0.001},
        )
    else:
        size_field = FieldSpec(
            "cloud.size_pixels", "Size (px)", "slider",
            {"min": 0.1, "max": 20.0, "step": 0.1},
        )
    fields_: list[FieldSpec] = [
        FieldSpec("cloud.style", "Style", "combobox",
                  {"choices": ["points", "square", "spheres"]}),
        size_field,
        FieldSpec("cloud.size_unit", "Size unit", "combobox",
                  {"choices": ["pixels", "meters"]}),
        FieldSpec("cloud.alpha", "Alpha", "slider",
                  {"min": 0.0, "max": 1.0, "step": 0.05}),
    ]
    if include_decay:
        fields_.append(FieldSpec("cloud.decay_seconds",
                                 "Decay time (s, 0 = off)", "spinbox_float",
                                 {"min": 0.0, "max": 600.0, "step": 1.0}))
    fields_.extend([
        FieldSpec("cloud.color_transformer", "Color transformer", "combobox",
                  {"choices": ["flat", "z", "intensity"]}),
        FieldSpec("cloud.flat_color", "Flat color", "color"),
        FieldSpec("cloud.color_min", "Color min", "spinbox_float",
                  {"min": -1000.0, "max": 1000.0, "step": 0.1}),
        FieldSpec("cloud.color_max", "Color max", "spinbox_float",
                  {"min": -1000.0, "max": 1000.0, "step": 0.1}),
    ])
    return fields_


def prior_map_schema() -> list[FieldSpec]:
    return [
        FieldSpec("prior_map.show", "Show on ground plane", "checkbox"),
        FieldSpec("prior_map.alpha", "Alpha", "slider",
                  {"min": 0.0, "max": 1.0, "step": 0.05}),
    ]


def background_schema() -> list[FieldSpec]:
    return [
        FieldSpec("background", "Background color", "color"),
    ]


def panel_tabs(include_decay: bool, size_unit: str,
               include_prior_map: bool = False
               ) -> list[tuple[str, str, list[FieldSpec]]]:
    """Return (tab_id, tab_label, fields) triples in display order."""
    tabs = [
        ("frames", "Frames", frames_schema()),
        ("cloud", "Cloud", cloud_schema(include_decay, size_unit)),
    ]
    if include_prior_map:
        tabs.append(("prior_map", "Prior Map", prior_map_schema()))
    tabs.append(("background", "Background", background_schema()))
    return tabs
```

- [ ] **Step 4: `settings_panel.py` — 가드 제거 + `rebuild_cloud_tab` + 콤보 hook 교체**

`pkrc_visualizer/widgets/settings_panel.py`에서 다음 변경:

(a) **상수 4개 + 가드 메서드 제거** — 파일 상단의 다음 블록을 삭제:

```
# Cross-mode safe defaults for cloud.size when the user toggles size_unit.
# Values that make sense in pixels are 6 orders of magnitude off in meters
# (and vice versa), so vtkPointGaussianMapper would otherwise paint giant
# splats and freeze the GPU. The threshold splits the two regimes.
SIZE_UNIT_SAFE_THRESHOLD = 1.0
SAFE_SIZE_PIXELS = 2.0
SAFE_SIZE_METERS = 0.05
```

그리고 `_guard_size_on_unit_change` 메서드 전체(`settings_panel.py:195-211`) 삭제.

(b) **콤보 hook 교체** — `_make_widget`의 combobox 분기에서:

```python
if spec.path == "cloud.size_unit":
    w.currentTextChanged.connect(self._guard_size_on_unit_change)
```

이 부분을 다음으로 교체:

```python
if spec.path == "cloud.size_unit":
    # Defer rebuild to the next event-loop tick: the combobox is a
    # child of the cloud tab that rebuild_cloud_tab will destroy, and
    # destroying a widget mid-signal-emission is unsafe in Qt.
    w.currentTextChanged.connect(
        lambda new_unit: QTimer.singleShot(
            0, lambda u=new_unit: self.rebuild_cloud_tab(u)))
```

(c) **`__init__` 에 _build_ui에서 사용한 tabs 보관** — schema callback 재호출을 위해 `include_decay`도 보관 필요. `__init__`에서 다음 두 줄을 추가:

```python
self._include_decay = any(
    spec.path == "cloud.decay_seconds"
    for tid, _, fields_ in tabs if tid == "cloud"
    for spec in fields_
)
```

(`__init__`에서 `self._build_ui(tabs)` 직전에 위 한 블록을 추가하면 됨.)

(d) **`rebuild_cloud_tab` 메서드 신설** — 클래스 본문 끝에 추가:

```python
def rebuild_cloud_tab(self, size_unit: str) -> None:
    """cloud 탭의 위젯 트리를 새 size_unit에 맞춰 다시 만든다.

    `cloud.size_unit` 콤보가 바뀌면 트리거된다. 슬라이더의
    path/range/label/step이 단위별로 다르므로 위젯을 in-place로
    갈아끼우기보다 cloud 탭 전체를 교체하는 편이 시그널·디바운스
    타이머 재연결 위험을 회피해 안전하다.

    호출자는 이 메서드 직후 apply_values(page)로 현재 값을 채워야
    한다 (base_page의 store changed 핸들러가 둘 다 호출).
    """
    from pkrc_visualizer.widgets.settings_schema import cloud_schema
    # 기존 cloud 탭 인덱스 찾기
    cloud_idx = self._tab_id_list.index("cloud")
    # 위젯 사전에서 cloud.* 항목 제거 (apply_values가 새 위젯에만 작용하도록)
    for path in [p for p in self._widgets if p.startswith("cloud.")]:
        self._widgets.pop(path)
        timer = self._debounce_timers.pop(path, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
    # 새 cloud 탭 빌드 (기존 _build_ui의 tab-loop 일부 재현)
    fields_ = cloud_schema(self._include_decay, size_unit)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    inner = QWidget()
    form = QFormLayout(inner)
    for spec in fields_:
        w = self._make_widget(spec)
        self._widgets[spec.path] = w
        form.addRow(QLabel(spec.label), w)
    scroll.setWidget(inner)
    # 기존 탭을 같은 인덱스에서 교체
    self._tabs_widget.removeTab(cloud_idx)
    self._tabs_widget.insertTab(cloud_idx, scroll, "Cloud")
    self._tabs_widget.setCurrentIndex(cloud_idx)
```

- [ ] **Step 5: `display_settings.py` — legacy `size` 필드 제거 + 가드 코드 삭제**

(a) **`CloudSettings`에서 `size: float = 2.0` 줄 삭제**:

```python
@dataclass
class CloudSettings:
    style: str = "points"
    # size: float = 2.0  ← 이 줄 삭제
    size_pixels: float = 1.0
    size_meters: float = 0.01
    ...
```

(b) **가드 함수/상수 삭제** — `display_settings.py:153-169`의 다음 블록 전체 삭제:

```python
# Atomic cross-field guard: ...
SIZE_UNIT_THRESHOLD = 1.0
SAFE_SIZE_FOR_PIXELS = 2.0
SAFE_SIZE_FOR_METERS = 0.05


def _safe_size_for_unit(unit: str, current: float) -> float:
    if unit == "meters" and current > SIZE_UNIT_THRESHOLD:
        return SAFE_SIZE_FOR_METERS
    if unit == "pixels" and current < SIZE_UNIT_THRESHOLD:
        return SAFE_SIZE_FOR_PIXELS
    return current
```

(c) **`DisplaySettingsStore.update`에서 hook 제거** — `display_settings.py:199-200`의:

```python
        if path == "cloud.size_unit":
            page.cloud.size = _safe_size_for_unit(value, page.cloud.size)
```

이 두 줄 삭제. 결과적으로 `update` 메서드는 `setattr` 후 바로 `changed.emit` + `_save_timer.start()` 흐름.

- [ ] **Step 6: `pyvista_view.py` — `c.size` → `c.active_size`**

`pkrc_visualizer/widgets/pyvista_view.py:464-466`의:

```python
            self._install_point_mapper(actor, c.size_unit, c.size)
            prop = actor.GetProperty()
            prop.SetPointSize(c.size)        # pixels mode only; gaussian uses SetScaleFactor
```

다음으로 교체:

```python
            size = c.active_size
            self._install_point_mapper(actor, c.size_unit, size)
            prop = actor.GetProperty()
            prop.SetPointSize(size)        # pixels mode only; gaussian uses SetScaleFactor
```

(`size = c.active_size`는 for 루프 내부 actor 두 개 모두에서 동일한 값이므로 루프 밖으로 뽑아도 무방하지만, 현재 구조 변경 최소화를 위해 루프 내부에 둠.)

- [ ] **Step 7: `base_page.py` — `panel_tabs`에 `size_unit` 전달 + size_unit 변경 감지**

`pkrc_visualizer/pages/base_page.py`의 `_install_settings_panel` 메서드(파일 50-87 라인)를 다음으로 교체. 변경점은 (1) `panel_tabs` 시그니처, (2) `_on_store_changed` 안에서 size_unit 변화 시 `rebuild_cloud_tab` 호출 가드. nonlocal로 직전 단위를 추적해 매 변경마다 rebuild 하지 않도록.

```python
    def _install_settings_panel(
        self,
        view: PyVistaView,
        page_key: str,
        store: DisplaySettingsStore,
        include_decay: bool,
        include_prior_map: bool = False,
    ) -> None:
        """Hook a SettingsButton + SettingsPanel onto a 3D view.

        Applies the store's current values immediately. Wires field
        changes back into the store. Re-applies the snapshot to the view
        whenever the store emits. Rebuilds the cloud tab when the
        size_unit changes so the slider's path/range/label match the
        active unit.
        """
        snapshot = store.get(page_key)
        last_size_unit = snapshot.cloud.size_unit
        panel = SettingsPanel(
            panel_tabs(include_decay, last_size_unit,
                       include_prior_map=include_prior_map),
            parent=view,
        )
        button = SettingsButton(view)

        def _on_button_clicked():
            panel.toggle(button.geometry())
            # Spec §5: hide orientation widget while panel is visible
            view._orient_widget.SetEnabled(0 if panel.isVisible() else 1)

        def _on_store_changed(emitted_key, settings):
            if emitted_key != page_key:
                return
            view.apply_display_settings(settings)
            nonlocal last_size_unit
            new_unit = settings.cloud.size_unit
            if new_unit != last_size_unit:
                panel.rebuild_cloud_tab(new_unit)
                last_size_unit = new_unit
            panel.apply_values(settings)

        button.clicked.connect(_on_button_clicked)
        panel.field_changed.connect(
            lambda path, value: store.update(page_key, path, value))
        panel.reset_requested.connect(
            lambda section: store.reset(page_key, section=section))
        store.changed.connect(_on_store_changed)

        view.apply_display_settings(snapshot)
        panel.apply_values(snapshot)
```

핵심:
- `snapshot`을 hookup **시작**에서 한 번 가져와 패널 생성 시 단위를 즉시 전달.
- `last_size_unit`은 closure-local nonlocal 변수 (별도 멤버 필요 없음).
- `_on_store_changed`에서 단위 변화 감지 → rebuild → apply_values 순서.

- [ ] **Step 8: 기존 테스트 갱신 — `test_display_settings.py`**

(a) **clamp 테스트 3개 삭제** — 다음 함수 전체 삭제:
- `test_store_clamps_size_on_unit_toggle_pixels_to_meters`
- `test_store_clamps_size_on_unit_toggle_meters_to_pixels`
- `test_store_keeps_safe_size_on_unit_toggle`

(b) **`size`를 직접 참조하던 테스트 갱신**:

`test_yaml_roundtrip` — `CloudSettings(size=5.0, ...)` → `CloudSettings(size_pixels=5.0, size_unit="pixels", ...)` 로 변경, assertion도 `cloud.size_pixels == 5.0`로:

```python
def test_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "slam": PageDisplaySettings(
            background="#000000",
            frames=FramesSettings(map_axes_length_m=2.5, label_font_size=24),
            cloud=CloudSettings(
                size_pixels=5.0, size_unit="pixels",
                color_transformer="z", color_max=20.0,
            ),
        ),
        "mapping": PageDisplaySettings(),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["slam"].background == "#000000"
    assert loaded["slam"].frames.map_axes_length_m == 2.5
    assert loaded["slam"].frames.label_font_size == 24
    assert loaded["slam"].cloud.size_pixels == 5.0
    assert loaded["slam"].cloud.size_unit == "pixels"
    assert loaded["slam"].cloud.color_transformer == "z"
    assert loaded["slam"].cloud.color_max == 20.0
    assert loaded["mapping"] == PageDisplaySettings()
```

`test_unknown_yaml_keys_dropped` — yaml에 `size: 7.0`을 그대로 두지만(legacy 마이그레이션이 처리), assertion을 `cloud.size_meters == 7.0` (default unit이 meters이므로)로:

```python
def test_unknown_yaml_keys_dropped(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "slam:\n"
        "  background: '#222222'\n"
        "  unknown_top_level: 42\n"
        "  frames:\n"
        "    map_axes_length_m: 3.0\n"
        "    future_field: 99\n"
        "  cloud:\n"
        "    size: 7.0\n"
        "    intensity_field_name: 'foo'\n"
    )
    loaded = load_yaml(path)
    assert loaded["slam"].background == "#222222"
    assert loaded["slam"].frames.map_axes_length_m == 3.0
    # legacy size=7.0 with default unit=meters → size_meters=7.0
    assert loaded["slam"].cloud.size_meters == 7.0
```

`test_store_update_emits_changed`:

```python
def test_store_update_emits_changed(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml")
    spy = QSignalSpy(store.changed)
    store.update("slam", "cloud.size_meters", 0.07)
    assert len(spy) == 1
    assert store.get("slam").cloud.size_meters == 0.07
```

`test_store_debounces_yaml_write`:

```python
def test_store_debounces_yaml_write(tmp_path, qtbot):
    path = tmp_path / "s.yaml"
    store = DisplaySettingsStore(path=path, debounce_ms=100)
    store.update("slam", "cloud.size_meters", 0.05)
    store.update("slam", "cloud.size_meters", 0.06)
    store.update("slam", "cloud.size_meters", 0.07)
    assert not path.exists()
    qtbot.wait(220)
    assert path.exists()
    assert load_yaml(path)["slam"].cloud.size_meters == 0.07
```

`test_store_reset_section`:

```python
def test_store_reset_section(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml")
    store.update("slam", "cloud.size_meters", 0.09)
    store.update("slam", "frames.label_font_size", 24)
    store.reset("slam", section="cloud")
    assert store.get("slam").cloud.size_meters == 0.01  # default
    assert store.get("slam").frames.label_font_size == 24  # untouched
```

`test_cloud_decay_max_points_legacy_key_silently_dropped` — `size: 4.0` legacy 처리:

```python
def test_cloud_decay_max_points_legacy_key_silently_dropped(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "slam:\n"
        "  cloud:\n"
        "    decay_max_points: 999999\n"
        "    size: 4.0\n"
    )
    loaded = load_yaml(path)
    assert loaded["slam"].cloud.decay_seconds == 30.0
    # legacy size=4.0 with default unit=meters → size_meters=4.0
    assert loaded["slam"].cloud.size_meters == 4.0
```

`test_cloud_size_unit_yaml_roundtrip` — `size=0.5` → `size_meters=0.5` 직접:

```python
def test_cloud_size_unit_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "slam": PageDisplaySettings(
            cloud=CloudSettings(size_unit="meters", size_meters=0.5),
        ),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["slam"].cloud.size_unit == "meters"
    assert loaded["slam"].cloud.size_meters == 0.5
```

- [ ] **Step 9: 기존 테스트 갱신 — `test_settings_panel.py`**

(a) **clamp 테스트 3개 삭제**:
- `test_size_unit_toggle_clamps_oversized_meters`
- `test_size_unit_toggle_clamps_undersized_pixels`
- `test_size_unit_toggle_keeps_safe_value`

(b) **panel_tabs 호출 시그니처 갱신** — `test_settings_panel.py` 안의 모든 `panel_tabs(...)` 호출이 새 시그니처(`include_decay, size_unit, ...`)에 맞도록:

```bash
grep -n "panel_tabs(" test/test_settings_panel.py
```

각 호출을 다음 패턴으로 갱신 (`size_unit`은 테스트 의도에 맞게 "pixels" 또는 "meters"):

```python
# before
panel_tabs(include_decay=True)
# after
panel_tabs(include_decay=True, size_unit="pixels")
```

(c) **schema 카운트 검증 갱신** — `test_settings_panel.py:74` 부근의 다음 주석/검증:

```python
# frames(9) + cloud(9 with decay+size_unit) + background(1)
```

이제 cloud 탭은 동일하게 9개 (style, size_<unit>, size_unit, alpha, decay_seconds, color_transformer, flat_color, color_min, color_max) — 카운트는 동일하므로 산술 부분은 변경 불필요. 위젯 키 검증에서 `"cloud.size"` 참조를 `"cloud.size_pixels"` 또는 `"cloud.size_meters"`로 갱신:

```bash
grep -n '"cloud.size"' test/test_settings_panel.py
```

각각 테스트 setup에서 사용하는 size_unit에 맞춰 갱신.

(d) **page에 cloud.size 직접 setter 사용 부분 갱신** — `test_settings_panel.py:89` 의:

```python
page.cloud.size = 7.0
```

는 다음으로 (테스트가 사용 중인 size_unit에 맞춰):

```python
page.cloud.size_pixels = 7.0   # if test uses pixels
# or
page.cloud.size_meters = 0.07  # if test uses meters
```

assertion도 동일하게 갱신.

- [ ] **Step 10: 기존 테스트 갱신 — `test_settings_integration.py`**

`test_settings_integration.py`에서 `panel._widgets["cloud.size"]` 참조 모두를 단위에 따라 `cloud.size_pixels` 또는 `cloud.size_meters`로 갱신. 그리고 `panel_tabs` 호출 시그니처에 `size_unit` 추가.

```bash
grep -n '"cloud.size"\|panel_tabs(' test/test_settings_integration.py
```

각 위치를 테스트 의도에 맞춰 단위별 경로로 갱신.

예시 패턴 (test_settings_integration.py:29-37 부근):

```python
# before:
store.update("slam", "cloud.size_unit", "pixels")
...
panel._widgets["cloud.size"].setValue(8.0)

# after:
store.update("slam", "cloud.size_unit", "pixels")
panel.rebuild_cloud_tab("pixels")  # size_unit 변경에 패널이 반응
panel._widgets["cloud.size_pixels"].setValue(8.0)
```

(통합 테스트 흐름에서는 이전에 store.update가 트리거하던 가드 대신, 패널의 rebuild를 명시적으로 호출. 통합 테스트는 base_page까지 보지 않으므로 패널 메서드 직접 호출.)

- [ ] **Step 11: 기존 테스트 갱신 — `test_pyvista_size_unit.py`**

`_apply` 헬퍼를 다음으로 교체 (`pkrc_visualizer/test/test_pyvista_size_unit.py:8-12`):

```python
def _apply(view, *, size_unit, size=2.0):
    s = PageDisplaySettings()
    s.cloud.size_unit = size_unit
    if size_unit == "meters":
        s.cloud.size_meters = size
    else:
        s.cloud.size_pixels = size
    view.apply_display_settings(s)
```

기존 테스트들의 assertion(예: `actor.GetProperty().GetPointSize() == 5.0`, `mapper.GetScaleFactor() == 0.5`)은 `c.active_size`가 size_pixels 또는 size_meters를 라우팅하므로 그대로 통과.

- [ ] **Step 12: 전체 테스트 실행 — 모두 통과해야 함**

```
cd /home/hero/ros2_ws
colcon build --packages-select pkrc_visualizer --symlink-install
source install/setup.bash
cd src/pkrc_visualizer
python -m pytest test/ -v
```

Expected: 모든 테스트 PASS. 기존 테스트 카운트에서 제거된 6개(display_settings 3 + settings_panel 3) 만큼 줄어들고, 새로 추가된 9개(Task 1: 4 + Task 2: 3 + Task 3: 3) 만큼 늘어남. 순증가 +3.

- [ ] **Step 13: 수동 스모크 테스트**

```
cd /home/hero/ros2_ws
source install/setup.bash
ros2 launch pkrc_visualizer pkrc_visualizer.launch.py
```

(1) SLAM 페이지 → settings 패널 열기 → cloud 탭 → size_unit을 pixels로 변경 → 슬라이더 라벨이 "Size (px)"로 바뀌고 range가 0.1–20으로 바뀌는지 확인. (2) 슬라이더를 10.0 으로 설정 → meters로 토글 → 슬라이더 라벨이 "Size (m)"로 바뀌고 값은 0.01(default)이어야 함, 4미터 splat이 발생하지 않음 → 다시 pixels로 토글 → 값이 10.0 그대로(무손실). (3) Sonar Mapping 페이지에서도 동일하게 작동하는지 확인.

- [ ] **Step 14: 커밋**

```
git add -A pkrc_visualizer/ test/
git commit -m "refactor: switch cloud size to per-unit storage, remove guard logic

- CloudSettings: drop legacy size; size_pixels/size_meters as the source of truth
- pyvista_view: render uses c.active_size which routes by size_unit
- settings_schema: cloud_schema(include_decay, size_unit) emits unit-specific FieldSpec
- settings_panel: rebuild_cloud_tab swaps cloud tab when size_unit changes
- base_page: passes current size_unit to panel_tabs and triggers rebuild on change
- display_settings: drop _safe_size_for_unit and SIZE_UNIT_*/SAFE_SIZE_* constants
- settings_panel: drop _guard_size_on_unit_change and SIZE_UNIT_SAFE_*/SAFE_SIZE_* constants
- tests: remove 6 obsolete clamp tests, update field references, add lossless toggle"
```

---

## Task 4: 버전 업 + CHANGELOG + README

스펙의 §"Versioning & changelog"를 그대로 반영.

**Files:**
- Modify: `package.xml`, `setup.py`, `CHANGELOG.md`, `README.md`

- [ ] **Step 1: 버전 번호 업**

`package.xml:5`:

```xml
<version>0.8.0</version>
```

`setup.py:7`:

```python
version='0.8.0',
```

- [ ] **Step 2: CHANGELOG 새 블록 추가**

`CHANGELOG.md` 의 `# Changelog` 다음에 다음 블록을 삽입 (`## [0.7.0]` 직전):

```markdown
## [0.8.0] — 2026-05-07

### Removed
- `CloudSettings.size` (단일 필드).
- `display_settings._safe_size_for_unit` 및 상수 `SIZE_UNIT_THRESHOLD`,
  `SAFE_SIZE_FOR_PIXELS`, `SAFE_SIZE_FOR_METERS`.
- `widgets.settings_panel._guard_size_on_unit_change` 및 상수
  `SIZE_UNIT_SAFE_THRESHOLD`, `SAFE_SIZE_PIXELS`, `SAFE_SIZE_METERS`.
- 단위 토글 시 store/panel 양 쪽에서 size를 임의 안전값으로 덮어쓰던
  중복 가드 — 더 이상 필요 없음.

### Added
- `CloudSettings.size_pixels` (default `1.0`), `CloudSettings.size_meters`
  (default `0.01`) — 단위별 사이즈 독립 저장.
- `CloudSettings.active_size` 프로퍼티 — `size_unit`에 따라 활성 단위
  필드를 반환. 렌더 경로 전용 read-only.
- `SettingsPanel.rebuild_cloud_tab(size_unit)` — `cloud.size_unit` 변경
  시 cloud 탭의 슬라이더(path/range/label/step)를 단위별로 교체.

### Changed
- `cloud_schema(include_decay, size_unit)`, `panel_tabs(include_decay,
  size_unit, include_prior_map=False)`로 시그니처 확장 — 활성 단위에
  맞는 슬라이더 spec을 emit.
- 슬라이더 range/step이 단위별로 분리: pixels `0.1–20.0` step `0.1`,
  meters `0.001–0.5` step `0.001`. 슬라이더 라벨도 자동 (`Size (px)` /
  `Size (m)`).
- 단위 토글이 무손실: 각 단위가 자기 사이즈를 기억하므로 px=10에서
  meter로 토글 후 다시 pixels로 돌아오면 10 그대로 유지.

### Migration
- 기존 yaml의 `cloud.size`는 `settings_from_dict` 안에서 활성 단위
  쪽 새 필드로 in-place 마이그레이션. 다른 단위는 dataclass 기본값
  (px=1.0, m=0.01)으로 채움. 신/구 키가 모두 있으면 새 키 우선.
- save_yaml은 더 이상 legacy `size` 키를 기록하지 않음.

### Verification
- `colcon build --packages-select pkrc_visualizer` PASS
- `pytest` PASS (기존 대비 순증 +3 테스트)
- 수동 (SLAM 페이지): pixels 10 → meters 토글 시 4-meter splat 발생
  하지 않고 0.01 m로 안전하게 시작; 다시 pixels 토글 시 10 복귀.
- 수동 (Sonar Mapping 페이지): SLAM과 동일 동작 확인.

### Notes
- 외부 패키지(fast-lio, sensor_packages 등)에 무영향 — cloud 데이터
  흐름·topic·QoS·frame_id 일절 변경 없음.
- 다음 작업 후보: 색상 다이얼로그(`QColorDialog` / `_ColorButton`)의
  배경 색상 변동 이슈 — 별도 PR로.

---
```

- [ ] **Step 3: README의 Settings 섹션 갱신**

`README.md`에서 cloud size 관련 단락을 찾아 (없으면 Settings/Display 섹션에 한 단락 추가) 다음으로 갱신:

> **Cloud point size**: pixels 모드와 meters 모드 사이즈가 각각 별도로
> 저장됩니다. 단위를 토글하면 슬라이더가 그 단위의 마지막 값으로 즉시
> 복귀합니다 (무손실). 기본값은 pixels=1.0 (모드 전환 시 즉시 가벼운
> 점), meters=0.01 (1 cm splat).

- [ ] **Step 4: 빌드 + 테스트 + 수동 스모크 한번 더**

```
cd /home/hero/ros2_ws
colcon build --packages-select pkrc_visualizer --symlink-install
source install/setup.bash
python -m pytest src/pkrc_visualizer/test/ -v
ros2 launch pkrc_visualizer pkrc_visualizer.launch.py
```

Expected: 빌드 PASS, 테스트 PASS, GUI 정상 동작 (Task 3 Step 13 의 시나리오 재확인).

- [ ] **Step 5: 커밋**

```
git add package.xml setup.py CHANGELOG.md README.md
git commit -m "chore(release): 0.8.0 — per-unit cloud size storage

See CHANGELOG.md for full notes."
```

- [ ] **Step 6: PR**

수동(또는 commit-push-pr 슬래시 명령). 사용자 명시 승인 시점에 진행.

```
git push -u origin <branch>
gh pr create --title "Per-unit cloud size storage (0.8.0)" --body "..."
```

PR 본문은 CHANGELOG 0.8.0 블록 + 수동 스모크 체크리스트 (`[ ] SLAM
무손실 토글`, `[ ] Sonar Mapping 무손실 토글`, `[ ] 기존 yaml 자동
마이그레이션 확인`) 형태.

---

## Self-Review (작성자 점검 — 실행 전 한번 더)

- **Spec coverage**: 스펙의 §Data model→Task 1, §YAML migration→Task 2,
  §Schema dynamic swap + §Removal of guard code + §Render path→Task 3,
  §Test plan→Task 1·2·3에 분산, §Versioning & changelog→Task 4. 모든
  스펙 섹션이 task에 매핑됨.
- **Placeholder scan**: 본 plan에 "TBD/TODO/적절히/적당히/handle errors"
  류 없음. 모든 step에 실제 코드/명령/예상 출력이 명시됨. 단,
  `base_page.py`의 정확한 멤버 이름(`self._store` vs `self._settings`
  등)은 실제 코드를 보고 조정하라고 지시 — 이는 placeholder가 아니라
  방어적 모호성 (실제 멤버 이름을 미확인 추측으로 박지 않음).
- **Type consistency**: 새 식별자 `size_pixels`, `size_meters`,
  `active_size`, `rebuild_cloud_tab(size_unit)`는 plan 전반에서 동일
  표기. `cloud_schema(include_decay, size_unit)` /
  `panel_tabs(include_decay, size_unit, include_prior_map=False)`도
  Task 3과 Task 4(CHANGELOG) 양쪽에서 일치.
- **Regression-safe ordering**: Task 1·2는 legacy `size`를 남겨둔
  채 새 필드만 추가 → 기존 테스트에 영향 없음. Task 3가 단일 커밋으로
  legacy 제거 + 모든 consumer 전환을 동시에 수행 → 중간 broken state
  최소화. Task 4는 메타파일만 건드리는 무위험 단계.
