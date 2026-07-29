# Cloud size per unit — design

**Date:** 2026-05-07
**Target package:** `pkrc_visualizer`
**Target version:** `0.7.0` → `0.8.0`
**Pages affected:** SLAM, Sonar Mapping (둘 다 동일한 `cloud_schema` / `CloudSettings` 공유)

## Problem

현재 `CloudSettings`는 단일 `size: float`와 `size_unit: str`로 cloud 점/스플랫 크기를 표현한다. pixel 모드에서 `size=4.0`이 합리적이어도, 사용자가 `size_unit`만 `meters`로 토글하면 그대로 `size=4.0 m` 가 되어 `vtkPointGaussianMapper`의 splat 반경이 4 m 가 되고 GPU가 멈춘다.

지금까지는 두 위치에 가드를 두어 이를 임시 방어해 왔다:

- `display_settings.DisplaySettingsStore.update` 안의 `_safe_size_for_unit` (store-side clamp)
- `widgets/settings_panel.SettingsPanel._guard_size_on_unit_change` (widget-side clamp)

가드 자체가 두 군데에 있는 이유는 store ↔ panel 간 디바운스 타이밍 때문에 한쪽만 있으면 짧게 위험값으로 렌더되는 프레임이 생기기 때문이다 (`display_settings.py:153-161` 코멘트).

이 가드는 다음 단점을 가진다:

1. 매직 임계값 `1.0`과 매직 안전값 `2.0`/`0.05`로 사용자의 의도를 임의 덮어씀.
2. 기존에 잘 맞춰둔 pixel 사이즈 4.0이 meter로 토글했다가 돌아오면 임의값 2.0으로 바뀌어 있음 — 무손실이 아님.
3. 동일한 클램프 로직이 두 곳에 중복.

## Proposal

`cloud.size`(단일 필드)를 `cloud.size_pixels` + `cloud.size_meters`(독립 필드 두 개)로 분리한다. 활성화된 단위가 어느 쪽이든 다른 단위의 값에 영향을 주지 않으므로 가드 자체가 불필요해진다.

## Goals

- 단위 토글이 무손실: pixel=4.0 → meters → pixel 복귀 시 4.0 그대로.
- 단위 토글 직후 GPU 멈춤이 일어나지 않음 (각 단위에 단위별 default가 보장되므로).
- 기존 사용자의 yaml 설정이 자동 마이그레이션됨.
- 두 곳의 가드(store/panel)와 매직 상수가 모두 사라짐.
- SLAM/Sonar Mapping 양 페이지 모두에 자동 반영 (schema 한 곳만 수정).

## Non-goals

- 색상 다이얼로그 배경 동작 변경 (별도 스펙으로 분리).
- pixel/meter 외 다른 단위 추가.
- size 외 다른 cloud 필드의 단위화.

## Data model

```python
@dataclass
class CloudSettings:
    style: str = "points"
    size_pixels: float = 1.0          # NEW — px 모드 사이즈
    size_meters: float = 0.01         # NEW — meter 모드 사이즈
    size_unit: str = "meters"         # 그대로
    alpha: float = 1.0
    decay_seconds: float = 30.0
    color_transformer: str = "flat"
    flat_color: str = "#4fc3f7"
    color_min: float = 0.0
    color_max: float = 10.0

    @property
    def active_size(self) -> float:
        return self.size_meters if self.size_unit == "meters" else self.size_pixels
```

- **제거**: `size: float = 2.0` (단일 필드).
- **신규**: `size_pixels`, `size_meters` 독립 필드 + `active_size` read-only 프로퍼티.
- 기본값: `size_pixels=1.0`, `size_meters=0.01` (사용자 요구).

## YAML migration

기존 yaml은 `cloud: {size: <X>, size_unit: <Y>}` 형태. 새 reader는 `_filter_known`이 모르는 키 `size`를 자동으로 버리는데, 그렇게 두면 사용자의 현재 사이즈가 조용히 사라진다. 따라서 `settings_from_dict` 안에서 명시적으로 in-place 마이그레이션한다.

```python
def settings_from_dict(d):
    cloud_raw = d.get("cloud", {})
    if (
        isinstance(cloud_raw, dict)
        and "size" in cloud_raw
        and "size_pixels" not in cloud_raw
        and "size_meters" not in cloud_raw
    ):
        legacy_size = cloud_raw.pop("size")
        unit = cloud_raw.get("size_unit", _DEFAULTS.cloud.size_unit)
        if unit == "meters":
            cloud_raw.setdefault("size_meters", legacy_size)
        else:
            cloud_raw.setdefault("size_pixels", legacy_size)
    cloud = CloudSettings(**_filter_known(CloudSettings, cloud_raw))
    ...
```

규칙:

- legacy `size` → 그 시점의 `size_unit`에 해당하는 새 필드로 복사.
- 다른 단위 필드는 dataclass 기본값(1.0/0.01)으로 자동 채움.
- 신/구 필드 모두 있는 yaml(예: 사용자가 직접 편집)은 새 필드 우선, legacy `size` 무시.
- `save_yaml`은 새 모델대로 `size_pixels`/`size_meters`만 직렬화 (legacy `size`는 더 이상 기록되지 않음).

## Schema dynamic swap

`cloud_schema`는 현재 `cloud.size`(단일 슬라이더, range 0.01–20.0, step 0.1)로 두 단위를 모두 커버한다. 새 모델에서는 단위에 따라 활성 슬라이더가 바뀌므로 시그니처에 현재 단위를 받는다.

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
    fields_ = [
        FieldSpec("cloud.style", "Style", "combobox",
                  {"choices": ["points", "square", "spheres"]}),
        size_field,
        FieldSpec("cloud.size_unit", "Size unit", "combobox",
                  {"choices": ["pixels", "meters"]}),
        FieldSpec("cloud.alpha", "Alpha", "slider",
                  {"min": 0.0, "max": 1.0, "step": 0.05}),
    ]
    # ... (decay/color_transformer/flat_color/color_min/color_max 그대로)
```

`panel_tabs(include_decay, include_prior_map, size_unit)`로 시그니처 확장. `base_page` 호출자도 현재 페이지의 `cloud.size_unit`을 넘기도록 갱신.

### 단위 토글 시 패널 부분 재빌드

`SettingsPanel`은 다음 메서드를 추가한다:

```python
def rebuild_cloud_tab(self, size_unit: str) -> None:
    """cloud 탭의 위젯 트리를 새 size_unit에 맞춰 다시 만든다.

    `cloud.size_unit` 콤보가 바뀌면 호출된다. 슬라이더의 path/range/label/step이
    단위별로 다르기 때문에, 위젯을 in-place로 재구성하는 것보다 cloud 탭 전체를
    재빌드하는 편이 시그널·디바운스 타이머 재연결 위험을 회피해 안전하다.
    """
```

- cloud 탭 인덱스를 찾아 `removeTab`, 새 `cloud_schema(include_decay, new_unit)`로 위젯 트리 재구성, 같은 인덱스에 `insertTab`.
- 기존 사용자 입력 중인 다른 cloud 필드(`alpha`, `flat_color` 등)도 함께 재빌드되지만, 즉시 `apply_values(page)`로 현재 값을 다시 채워 넣으므로 시각적 깜빡임 외에는 부작용 없음.
- `cloud.size_unit` 콤보 자체의 시그널 → store 갱신 → store changed 시그널 → page가 `apply_values` + `rebuild_cloud_tab`을 호출하는 흐름.

## Removal of guard code

다음을 모두 제거:

- `display_settings.py`
  - 상수: `SIZE_UNIT_THRESHOLD`, `SAFE_SIZE_FOR_PIXELS`, `SAFE_SIZE_FOR_METERS`
  - 함수: `_safe_size_for_unit`
  - `DisplaySettingsStore.update` 안의 `cloud.size_unit` 분기 후 `page.cloud.size = _safe_size_for_unit(...)` 호출
- `widgets/settings_panel.py`
  - 상수: `SIZE_UNIT_SAFE_THRESHOLD`, `SAFE_SIZE_PIXELS`, `SAFE_SIZE_METERS`
  - 메서드: `_guard_size_on_unit_change`
  - `_make_widget`의 `combobox` 분기에서 `cloud.size_unit` 핸들러 연결 부분 (대신 `rebuild_cloud_tab` 트리거로 교체)

## Render path (`pyvista_view._apply_cloud`)

`c.size` 참조를 `c.active_size`로 단순 치환:

```python
size = c.active_size
for actor in (self._cloud_actor, self._accum_actor):
    self._install_point_mapper(actor, c.size_unit, size)
    prop = actor.GetProperty()
    prop.SetPointSize(size)
    ...
    if isinstance(mapper, vtk.vtkPointGaussianMapper):
        mapper.SetSplatShaderCode(...)
        # SetScaleFactor는 _install_point_mapper 안에서 동일 size로 설정됨
```

mapper swap 로직(`_install_point_mapper`), splat shader 코드 분기, 그 외 cloud 처리 흐름은 무수정.

## Test plan

### 제거 (의미가 사라짐)

- `test/test_settings_panel.py::test_size_unit_toggle_clamps_oversized_meters`
- `test/test_settings_panel.py::test_size_unit_toggle_clamps_undersized_pixels`
- `test/test_settings_panel.py::test_size_unit_toggle_keeps_safe_value`

### 수정 (path/필드명 갱신)

- `test/test_pyvista_size_unit.py::_apply` 헬퍼 — `s.cloud.size_meters = size if unit == "meters" else _DEFAULTS.cloud.size_meters` 형태로 분기.
- `test/test_settings_integration.py` — `panel._widgets["cloud.size"]` → 단위에 따라 `cloud.size_pixels` 또는 `cloud.size_meters`.
- `test/test_display_settings.py`
  - 기본값 검증: `size_pixels == 1.0`, `size_meters == 0.01`.
  - reset 검증: 기본값 비교 대상 갱신.

### 신규

- `test/test_display_settings.py::test_cloud_size_per_unit_round_trip` — 두 필드를 다른 값으로 설정 → save → load 후 양 값 보존.
- `test/test_display_settings.py::test_cloud_size_legacy_migration_meters` — `cloud: {size: 4.0, size_unit: meters}` 입력 → `size_meters == 4.0`, `size_pixels == 1.0`.
- `test/test_display_settings.py::test_cloud_size_legacy_migration_pixels` — `cloud: {size: 8.0, size_unit: pixels}` 입력 → `size_pixels == 8.0`, `size_meters == 0.01`.
- `test/test_display_settings.py::test_cloud_size_legacy_ignored_when_new_present` — 새/구 키가 모두 있으면 새 키 우선, legacy 무시.
- `test/test_settings_panel.py::test_size_unit_toggle_swaps_active_slider` — `cloud.size_unit` 변경 후 cloud 탭에 `cloud.size_pixels` ↔ `cloud.size_meters` 위젯이 노출되고 라벨/range가 단위에 맞게 변경됨.
- `test/test_settings_panel.py::test_size_unit_toggle_is_lossless` — `size_pixels=10.0` 설정 → meters로 토글 → pixels로 복귀 시 슬라이더 값이 10.0 그대로 (회귀 방지 핵심).
- `test/test_pyvista_apply_settings.py::test_active_size_routes_per_unit` — `size_unit=meters`이면 `c.active_size == c.size_meters`, `pixels`이면 `c.active_size == c.size_pixels`. 그리고 mapper에 그 값이 전달되는지 (기존 파일에 추가, 신규 파일 만들지 않음).

## Versioning & changelog

- `package.xml` `0.7.0` → `0.8.0`
- `setup.py` 동일
- `CHANGELOG.md` 새 블록 (`## [0.8.0] — 2026-MM-DD`):
  - **Removed**: `CloudSettings.size`, `_safe_size_for_unit`, `SIZE_UNIT_THRESHOLD`/`SAFE_SIZE_FOR_PIXELS`/`SAFE_SIZE_FOR_METERS` (display_settings), `SIZE_UNIT_SAFE_THRESHOLD`/`SAFE_SIZE_PIXELS`/`SAFE_SIZE_METERS` (settings_panel), `_guard_size_on_unit_change`.
  - **Added**: `CloudSettings.size_pixels` (default 1.0), `CloudSettings.size_meters` (default 0.01), `CloudSettings.active_size` 프로퍼티, `SettingsPanel.rebuild_cloud_tab(size_unit)`.
  - **Changed**: cloud size 슬라이더의 path/label/range/step이 활성 단위에 따라 동적으로 swap. 단위 토글이 무손실. `cloud_schema`/`panel_tabs` 시그니처에 `size_unit` 인자 추가.
  - **Migration**: 기존 yaml의 `cloud.size`는 자동으로 활성 단위 쪽 새 필드로 이전, 다른 단위는 새 기본값.
  - **Verification**: colcon build PASS, pytest PASS, SLAM 페이지 수동 토글 무손실 확인, Sonar Mapping 페이지 동일 확인.
  - **Notes**: 외부 패키지(fast-lio, sensor_packages 등)에 무영향. cloud 데이터 흐름·toptic·QoS·frame_id 일절 변경 없음.
- `README.md` "Settings" 섹션 한 단락 갱신 — "각 단위가 자기 사이즈를 기억하므로 단위 토글이 무손실" 동작 설명.

## Out-of-scope (다음 작업)

- 색상 다이얼로그(`QColorDialog`) 또는 `_ColorButton` 배경 색상 변동 이슈 — 별도 스펙/PR.

## Open questions

- (해결됨) UI: 단일 슬라이더 + 단위에 따라 자동 swap.
- (해결됨) 마이그레이션: 활성 단위 쪽으로만 이전, 다른 단위는 기본값.
- (해결됨) 슬라이더 range/step: pixels 0.1–20.0/0.1, meters 0.001–0.5/0.001.
