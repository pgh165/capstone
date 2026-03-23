# 배선도 (Wiring Diagram)

## Raspberry Pi 4 GPIO 핀 연결

### RGB LED (공통 캐소드)

| LED 핀 | GPIO | 물리 핀 | 비고 |
|--------|------|---------|------|
| Red    | GPIO 17 | Pin 11 | 330Ω 저항 연결 |
| Green  | GPIO 27 | Pin 13 | 330Ω 저항 연결 |
| Blue   | GPIO 22 | Pin 15 | 330Ω 저항 연결 |
| GND    | GND     | Pin 9  | 공통 캐소드 |

### 능동 부저

| 부저 핀 | GPIO | 물리 핀 | 비고 |
|---------|------|---------|------|
| Signal (+) | GPIO 18 (PWM) | Pin 12 | PWM 제어 |
| GND (-)    | GND           | Pin 14 | |

### DHT22 온습도 센서

| DHT22 핀 | GPIO | 물리 핀 | 비고 |
|----------|------|---------|------|
| VCC (1)  | 3.3V | Pin 1   | 3.3V 전원 |
| Data (2) | GPIO 4 | Pin 7 | 10kΩ 풀업 저항 (VCC와 Data 사이) |
| NC (3)   | -    | -       | 미사용 |
| GND (4)  | GND  | Pin 6   | |

### MH-Z19B CO₂ 센서 (UART)

| MH-Z19B 핀 | GPIO | 물리 핀 | 비고 |
|-------------|------|---------|------|
| VCC         | 5V   | Pin 2   | 5V 전원 필수 |
| GND         | GND  | Pin 6   | |
| TX          | GPIO 15 (RXD) | Pin 10 | 센서 TX → RPi RX |
| RX          | GPIO 14 (TXD) | Pin 8  | 센서 RX → RPi TX |

> UART 사용을 위해 `/boot/config.txt`에 `enable_uart=1` 설정 필요.
> Bluetooth와 UART 충돌 시 `dtoverlay=disable-bt` 추가.

### Pi Camera V2

| 연결 | 위치 | 비고 |
|------|------|------|
| CSI 리본 케이블 | CSI 포트 | 카메라 보드의 파란면이 이더넷 포트 방향 |

> `raspi-config`에서 카메라 인터페이스 활성화 필요.

---

## 전체 배선 요약

```
Raspberry Pi 4
┌──────────────────────┐
│  [Pin 1]  3.3V ──────┼──── DHT22 VCC
│  [Pin 2]  5V   ──────┼──── MH-Z19B VCC
│  [Pin 6]  GND  ──────┼──── DHT22 GND / MH-Z19B GND
│  [Pin 7]  GPIO4 ─────┼──── DHT22 Data (+ 10kΩ 풀업)
│  [Pin 8]  GPIO14 ────┼──── MH-Z19B RX
│  [Pin 9]  GND  ──────┼──── LED GND
│  [Pin 10] GPIO15 ────┼──── MH-Z19B TX
│  [Pin 11] GPIO17 ────┼──── LED Red (330Ω)
│  [Pin 12] GPIO18 ────┼──── Buzzer Signal
│  [Pin 13] GPIO27 ────┼──── LED Green (330Ω)
│  [Pin 14] GND  ──────┼──── Buzzer GND
│  [Pin 15] GPIO22 ────┼──── LED Blue (330Ω)
│  [CSI]    Camera ─────┼──── Pi Camera V2
└──────────────────────┘
```

## 주의사항

1. MH-Z19B는 **5V 전원**이 필요하지만, UART 신호는 3.3V 레벨이므로 RPi에 직접 연결 가능
2. DHT22의 Data 핀에는 **10kΩ 풀업 저항**을 VCC(3.3V)와 사이에 연결
3. RGB LED 각 핀에는 **330Ω 저항**을 직렬 연결하여 전류 제한
4. 부저는 **능동 부저**를 사용하면 별도의 발진회로 불필요
5. UART 통신 속도: **9600bps** (MH-Z19B 기본값)
