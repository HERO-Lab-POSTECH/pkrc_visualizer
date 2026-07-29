# PKRC Visualizer — Monitoring Page (D6 Subscriber Side)

**Date**: 2026-05-07
**Scope**: `pkrc_visualizer` 패키지에 신규 "Monitoring" 페이지 1개 추가. D6 spec(Jetson 측 publisher)에서 발행하는 5개 토픽 + 기존 토픽 4개를 한 화면에 표시. **이번 라운드는 read-only(모니터링)에만 한정** — 양방향 조작(시동/릴레이/감도 publisher)은 별도 라운드.
**Status**: Design — implementation gated on user review.

## What

기존 `pkrc_visualizer`에 다섯 번째 페이지 **MonitoringPage**를 추가한다. 햄버거 메뉴 **첫 항목**으로 등록되며, 앱 시작 시 **기본 페이지**로 표시된다.

한 화면 안에 위젯들이 **2단 고정 격자**로 배치되어 동시에 보인다.

**상단 상태 바 (높이 20%)** — 6개의 작은 상태 위젯이 가로로 나열:

| # | 위젯 | 토픽 | 타입 |
|---|---|---|---|
| 1 | 조이스틱 입력 | `/joy` | `sensor_msgs/Joy` |
| 2 | 모터 전류 4채널 | `/pkrc/motors/cmd_current` | `Float32MultiArray[4]` |
| 3 | 배터리 잔량 | `/pkrc/battery/state` | `sensor_msgs/BatteryState` |
| 4 | 릴레이 LED 3개 | `/pkrc/relays/state` | `UInt8` (3-bit bitmask) |
| 5 | 소나 틸트 각도 | `/sonar/tilt/current_angle`, `/sonar/tilt/goal_angle` | `std_msgs/Float32` |
| 6 | 시동/감도/Lumen + LED 색 | `/pkrc/system/state`, `/pkrc/led/color` | `Float32MultiArray[3]`, `String` |

**하단 메인 영역 (높이 80%)** — 3개의 큰 시각화 패널이 가로로 균등 분할:

| # | 위젯 | 토픽 | 비고 |
|---|---|---|---|
| A | 2D 탑뷰 맵 + 로봇 pose | `/slam/fast_lio/odometry` (+ TF map↔odom) | paintEvent 기반 |
| B | 소나 데이터 | (미정 — 이번 라운드 placeholder) | "Sonar view — TBD" 텍스트만 |
| C | 카메라 영상 | `/camera/image/compressed` | QPixmap 디코드 |

**현재 라운드에서 제외:**
- 양방향 조작 (버튼/슬라이더로 명령 publish) — Jetson 측 subscriber 미구현 상태이므로 다음 라운드.
- 카메라 영상 위에 오버레이(소나 데이터, 검출 결과 등) — 현재 라운드는 단순 표시.
- 사용자 정의 위젯 재배치(dock) — 고정 격자만.

## Why

### 배경
사용자는 기존 `WebGUIModule`(브라우저 기반 `http://192.168.0.13:5000/`)을 모니터링 화면으로 사용해 왔다. 그러나 rosbridge-WebSocket-브라우저 경로는 100ms~수백ms 지연을 만들어 실시간성이 부족하다. D6 spec이 ROS 2 토픽 직접 발행을 결정한 뒤(2026-05-06), 외부 PC `pkrc_visualizer`에 같은 데이터를 받아 표시하는 **수신 측**이 필요해졌다.

### 핵심 설계 결정

**1. 신규 페이지를 첫 번째 페이지로 배치.**
사용자가 가장 자주 보는 화면이고, 운용 중 실시간 모니터링이 핵심 use-case. 기존 SLAM/Pose/Mapping/Image 페이지는 그대로 유지하고, `MainWindow.PAGE_TITLES` 맨 앞에 삽입.

**2. 고정 격자 레이아웃 (`QGridLayout`).**
대안: ImagePage처럼 `QDockWidget` 기반 사용자 재배치. 기각. 이유:
- 모니터링은 "한눈에 보는" 목적 — 매번 다른 위치에 있으면 인지 부담 증가
- 운용자가 위젯을 옮기다 잘못 닫는 사고 방지
- 코드 단순(고정 grid 인덱스)

**3. 토픽 등록 위치.**
대안 a: `topic_config.py`의 `TOPICS["monitoring"]`에 신규 페이지로 등록.
대안 b: 페이지 내부에서 `subscribe_dynamic` 사용.
**선택: a (TOPICS 등록)** — D6 토픽들은 정적이고 항상 존재. 동적 발견이 필요 없음. 기존 SLAM/Pose/Mapping 페이지와 일관된 패턴.

**4. 위젯은 페이지 내부 헬퍼 클래스로.**
`pkrc_visualizer/widgets/`에 새 위젯들을 흩뿌리는 대신, **`pkrc_visualizer/pages/monitoring/`** 하위 디렉토리에 페이지 전용 위젯들을 모아둔다. 이유:
- 다른 페이지에서 재사용 안 함 — `widgets/`는 PyVistaView처럼 공유되는 것만
- 추후 모니터링 페이지를 통째로 수정할 때 한 디렉토리만 보면 됨
- 페이지가 9개 위젯으로 복잡해지므로 `monitoring_page.py` 단일 파일은 너무 커짐

**5. 카메라 디코딩.**
`CompressedImage.data`(JPEG 바이트) → `QPixmap.loadFromData()` 직접 디코드. OpenCV 의존 추가 안 함. 디코드는 1회 + 위젯 크기에 맞춰 `QPixmap.scaled(KeepAspectRatio, FastTransformation)`. 30Hz JPEG(640×480)은 PyQt5 단독으로 처리 가능.

**6. 2D 맵 위젯 구현.**
대안 a: PyVistaView 재사용(3D 카메라를 위에서 본 것).
대안 b: 자체 `QWidget.paintEvent`로 2D 그리기.
**선택: b (커스텀 paintEvent)** — 이유:
- PyVista는 OpenGL 컨텍스트 무거움. 한 화면에 9개 위젯 중 하나로 쓰기엔 과함.
- 표시할 게 단순(원점, 격자, 로봇 화살표, 짧은 trail) — 200줄 이내 paintEvent.
- 같은 화면에 카메라 + 다른 위젯들과 OpenGL 컨텍스트 충돌 위험 회피.

맵의 `OccupancyGrid` 자체는 표시하지 않음(이번 라운드 범위 외) — 단순히 격자(grid) 배경 + 로봇 pose + 30초 trail.

## Architecture

### 디렉토리 구조

```
pkrc_visualizer/
├── pages/
│   ├── monitoring_page.py          # NEW — 페이지 컨테이너 (QGridLayout)
│   └── monitoring/                  # NEW — 페이지 전용 위젯들
│       ├── __init__.py
│       ├── camera_widget.py         # CompressedImage → QPixmap
│       ├── topdown_map_widget.py    # 2D 맵 + pose (paintEvent)
│       ├── joystick_widget.py       # /joy 시각화 (axes/buttons)
│       ├── motor_currents_widget.py # 4채널 막대
│       ├── relay_lamps_widget.py    # 3개 LED dot
│       ├── battery_widget.py        # voltage/% /상태
│       ├── system_state_widget.py   # 시동/감도/Lumen 텍스트
│       ├── led_color_widget.py      # 색 박스
│       └── sonar_tilt_widget.py     # 현재/목표 각도
├── topic_config.py                  # MODIFIED — TOPICS["monitoring"] 추가
└── main_window.py                   # MODIFIED — 페이지 등록 + 시작 인덱스
```

### 토픽 등록 (`topic_config.py`)

```python
from sensor_msgs.msg import BatteryState, CompressedImage, Joy
from std_msgs.msg import Float32, Float32MultiArray, String, UInt8

TOPICS["monitoring"] = [
    TopicSpec("mon_camera",      "/camera/image/compressed", CompressedImage, qos_best_effort=True),
    TopicSpec("mon_odom",        "/slam/fast_lio/odometry",  Odometry),
    TopicSpec("mon_joy",         "/joy",                     Joy, qos_best_effort=True),
    TopicSpec("mon_motors",      "/pkrc/motors/cmd_current", Float32MultiArray, qos_best_effort=True),
    TopicSpec("mon_relays",      "/pkrc/relays/state",       UInt8, qos_best_effort=True),
    TopicSpec("mon_battery",     "/pkrc/battery/state",      BatteryState, qos_best_effort=True),
    TopicSpec("mon_system",      "/pkrc/system/state",       Float32MultiArray, qos_best_effort=True),
    TopicSpec("mon_led",         "/pkrc/led/color",          String, qos_best_effort=True),
    TopicSpec("mon_tilt_cur",    "/sonar/tilt/current_angle", Float32, qos_best_effort=True),
    TopicSpec("mon_tilt_goal",   "/sonar/tilt/goal_angle",   Float32, qos_best_effort=True),
]
```

QoS는 D6 spec에 맞춰 모두 BEST_EFFORT. odometry는 publisher가 RELIABLE이지만 subscriber가 BEST_EFFORT면 **DDS 호환 규칙상 매칭됨** (RELIABLE pub ↔ BEST_EFFORT sub은 가능, 역은 불가).

### 페이지 컨테이너 (`monitoring_page.py`)

```python
class MonitoringPage(BasePage):
    """3×3 고정 격자 — 9개 모니터링 위젯."""

    TOPIC_PREFIX = "mon_"

    def __init__(self, ros_client, parent=None):
        super().__init__(ros_client, parent)
        self._build_layout()

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id.startswith(self.TOPIC_PREFIX)

    def _build_layout(self) -> None:
        # 2단 레이아웃: 상단 20% 상태 바 + 하단 80% 메인 영역.
        # top: [Joy][Motor][Battery][Relay][Tilt][Sys+LED] (QHBoxLayout)
        # bottom: [2D Map][Sonar TBD][Camera] (QHBoxLayout)
        ...

    def refresh(self) -> None:
        # 매 100ms (10Hz) — 각 위젯에 최신 캐시 전달
        for tid, msg in list(self._latest.items()):
            self._dispatch(tid, msg)

    def _dispatch(self, topic_id: str, msg) -> None:
        # topic_id → 해당 위젯의 update() 호출
        ...
```

`BasePage.refresh()`가 활성 페이지일 때만 10Hz로 돈다. 비활성 페이지는 타이머 멈춤(`hideEvent`) — 기존 패턴 그대로 사용.

### 격자 레이아웃 (2단)

```
+-------+-------+-------+-------+-------+-------+
|  Joy  | Motor | Batt  | Relay | Tilt  | Sys+  |  ← 높이 20%
|       |       |       |       |       | LED   |
+-------+-------+-------+-------+-------+-------+
|                                                |
|                                                |
|   [2D Map]    [Sonar TBD]    [Camera]          |  ← 높이 80%
|                                                |
|                                                |
+------------------------------------------------+
```

구현: `QVBoxLayout` 안에 두 개의 컨테이너 위젯.
- 상단: `QHBoxLayout` + 6개 상태 위젯 (각 위젯 stretch=1, 높이 고정)
- 하단: `QHBoxLayout` + 3개 메인 위젯 (각 stretch=1)
- 두 컨테이너 stretch 비율 1:4 (20% : 80%)

배경은 기존 `MainWindow` 다크 테마(`#2d2d30` 계열) 따라감.

### 데이터 흐름

```
RosClient (별도 스레드, rclpy.spin)
     │ message_received(topic_id, msg)
     │ Qt.QueuedConnection (스레드 안전)
     ↓
MonitoringPage._on_message
     │ self._latest[topic_id] = msg  (캐시)
     ↓
MonitoringPage.refresh (10Hz QTimer, 메인 스레드)
     │ self._dispatch(topic_id, msg)
     ↓
각 위젯.update_from_msg(msg)
     │
     ↓
위젯 내부에서 self.update() (paintEvent 트리거) 또는 setText()
```

10Hz로 통일하는 이유:
- 카메라(30Hz)도 10Hz로 다운샘플 — 모니터링 화면에선 충분, CPU/GPU 절약
- 사람 눈은 10Hz와 30Hz 차이를 모니터링 화면에선 거의 못 느낌
- 기존 페이지들도 모두 10Hz — 일관성

### `MainWindow` 수정

```python
PAGE_TITLES = ["Monitoring", "SLAM", "Pose / Path", "Sonar Mapping", "Sonar Image"]
#               ^^^^^^^^^^^^ NEW — 첫 번째

# in __init__:
self._stack.addWidget(MonitoringPage(ros_client))         # NEW — index 0
self._stack.addWidget(SlamPage(ros_client, display_store)) # 기존 → index 1
self._stack.addWidget(PosePage(ros_client))                # 기존 → index 2
self._stack.addWidget(MappingPage(ros_client, display_store))
self._stack.addWidget(ImagePage(ros_client, display_store))

# 시작 인덱스는 이미 0이므로 별도 변경 불필요 — 자동으로 Monitoring이 시작 페이지.
self._drawer.select(0)
self._stack.setCurrentIndex(0)
```

## 위젯별 표시 사양

### 1. CameraWidget
- `CompressedImage.data` → `QPixmap.loadFromData(data, "JPEG")`
- `QLabel.setPixmap(pixmap.scaled(self.size(), KeepAspectRatio, FastTransformation))`
- 데이터 없을 때: 회색 "No camera signal" 텍스트.

### 2. TopdownMapWidget
- 자체 `paintEvent`로 그림.
- 배경: 회색(#1e1e1e) + 1m 간격 격자(#3a3a3a).
- 좌표계: world(map) frame, +x → 화면 위, +y → 화면 왼쪽 (ENU 변환).
- 줌: 고정 5m × 5m 가시 영역 (로봇 중심).
- 로봇: 0.4m 길이 화살표(yaw 표시).
- Trail: 30초 슬라이딩 윈도우, 옅은 파란색 폴리라인.
- TF map↔odom 변환 적용(`ros_client.lookup_map_from_odom()`). 변환 없으면 odom frame 그대로 사용.

### 3. JoystickWidget
- `Joy.axes`(보통 8개)와 `Joy.buttons`(보통 11개)를 텍스트로 한 줄씩 표시.
- 시각화 버전(원형 디스플레이)은 다음 라운드.

### 4. MotorCurrentsWidget
- 4채널 가로 막대. 각 막대 옆에 숫자(소수점 2자리, 단위 A).
- 음/양 모두 처리(중심 0 기준 좌우).
- 절대값 > 임계치(예: 30A)일 때 빨간색.

### 5. RelayLampsWidget
- 비트마스크에서 각 비트 추출 → CH1/CH2/CH3 라벨 옆 원형 LED.
- ON: 녹색(#4caf50), OFF: 어두운 회색(#444).

### 6. BatteryWidget
- 전압(소수점 2자리, V) 큰 글자.
- 퍼센티지(%) + 막대(가로 30px).
- 상태 라벨: GOOD(녹색)/LOW(주황)/CRITICAL(빨강) — `power_supply_health` 매핑.

### 7. SystemStateWidget
- "ARMED: ON / OFF" (큰 글자, ON이면 녹색, OFF면 빨강).
- "감도: NN" (0~100 정수).
- "Lumen: NN%" (0~100 정수).

### 8. LedColorWidget
- 색 이름 텍스트 + 그 옆 30×30px 색 박스.
- "green" → `#4caf50`, "orange" → `#ff9800`, "blue" → `#2196f3`, "red" → `#f44336`, "off" → `#222`, 기타 → 회색.

### 9. SonarTiltWidget
- "현재: NN.N°" / "목표: NN.N°" 두 줄.
- 차이 > 5°일 때 회색 → 노란색.

## Trade-offs Considered

| 결정 | 대안 | 선택 이유 |
|---|---|---|
| 새 페이지로 추가 | 기존 페이지 수정 | D6 접근에서 명시 — "한 화면에 다 보이는" 새 모드 필요 |
| 햄버거 메뉴 첫 항목 | 마지막 항목 | 사용자 명시: "처음 키면 나오게" |
| 고정 격자 (QGridLayout) | QDockWidget 재배치 | 모니터링 = 한눈에 보는 것; 인지 부담 ↓; 코드 ↓ |
| 페이지 전용 widgets/ 서브디렉토리 | `widgets/` 평면 배치 | 9개 위젯이 다른 페이지에서 쓰일 일 없음; 응집도 ↑ |
| 카메라 PyQt5 직접 디코드 | OpenCV 도입 | 새 의존성 회피; QPixmap이 JPEG 디코드 가능 |
| 2D 맵: paintEvent | PyVistaView 재사용 | 한 화면에 9개 위젯 중 하나엔 OpenGL 과함 |
| `topic_config.py`에 정적 등록 | `subscribe_dynamic` | D6 토픽은 항상 존재; 기존 페이지와 일관 |
| 모든 토픽 BEST_EFFORT | RELIABLE 일부 | D6 spec 정책; odom RELIABLE pub ↔ BEST sub OK |
| 10Hz 통일 refresh | 토픽별 native rate | 일관성; CPU 절약; 사람 눈 충분 |
| 이번 라운드 read-only | 양방향 조작 포함 | 사용자 단계적 진행 결정; Jetson sub 미구현 |

## Risks

1. **PyQt5의 PyQt5 JPEG 디코드 성능** — 30Hz × 640×480 JPEG을 10Hz로 다운샘플하지만, 매 호출 디코드 시 5~10ms. 모니터링 페이지 활성 동안 CPU ~5% 추가. 허용 범위.
2. **QGridLayout과 화면 크기** — 1280×800 기준 설계. 작은 화면(예: 노트북 1366×768)에서 위젯이 겹칠 수 있음. `setMinimumSize` 보수적으로 설정 + 스크롤 영역으로 감쌈(`QScrollArea`).
3. **TF lookup 실패** — `lookup_map_from_odom`이 None 반환 시(SLAM 미시작) 맵 위젯이 odom frame으로 그대로 그림. trail이 origin 주변에 누적. 사용자 경험 허용 범위.
4. **PyQtWebEngine 같은 무거운 의존성 회피** — 명시적으로 도입 안 함. `requirements.txt` 변경 없음.
5. **빈 메시지 처리** — `Float32MultiArray.data`가 빈 배열일 때 인덱스 에러. 각 위젯에서 길이 검증.
6. **`/joy` 게임패드 필드 가변** — 패드 종류에 따라 axes/buttons 개수 다름. 텍스트 표시이므로 동적 처리 가능.

## Verification

```bash
# 빌드
cd ~/ros2_ws
colcon build --packages-select pkrc_visualizer
source install/setup.bash

# 실행
ros2 launch pkrc_visualizer pkrc_visualizer.launch.py

# 또는 직접
ros2 run pkrc_visualizer pkrc_viz
```

**확인 항목:**
- [ ] 앱 시작 시 "Monitoring" 페이지가 첫 화면으로 보임
- [ ] 햄버거 메뉴 첫 항목이 "Monitoring", 나머지 4개 페이지 그대로
- [ ] 9개 위젯이 한 화면에 모두 보임
- [ ] Jetson 토픽이 흐를 때 카메라/모터/배터리/릴레이/시동/LED/소나 틸트가 실시간 갱신
- [ ] `/slam/fast_lio/odometry`가 흐를 때 2D 맵에 로봇 위치/방향이 갱신, trail이 그려짐
- [ ] 다른 페이지로 이동하면 Monitoring 위젯들이 멈춤(timer 정지)
- [ ] 다시 Monitoring으로 돌아오면 즉시 갱신 재개
- [ ] 토픽이 흐르지 않을 때 위젯이 "데이터 없음" 또는 마지막 값을 보여주고 앱이 안 죽음

## Out of Scope (향후 라운드)

- **양방향 조작**: 시동 버튼, 릴레이 토글, 감도 슬라이더 — Qt에서 명령 토픽 publish + Jetson 측 subscriber 구현. 별도 spec.
- **카메라 위 오버레이**: 검출 박스, 소나 fan 오버레이 등.
- **Dock 기반 사용자 재배치**.
- **다중 카메라**: 현재 `/camera/image/compressed` 1개만.
- **소나 이미지/3D**: 기존 ImagePage / MappingPage가 담당.

## Open Questions

없음 (정책 확정).

## Rollback

- `git revert` 1 commit으로 완전 복구.
- 신규 파일 9개 + 수정 파일 2개(`topic_config.py`, `main_window.py`).
- 기존 4개 페이지(SLAM/Pose/Mapping/Image)는 한 줄도 수정 안 함 — 회귀 위험 없음.
- 새 토픽 구독 9개 추가가 부담이면 `topic_config.py`에서 `TOPICS["monitoring"]` 통째로 주석 처리 가능.
