import streamlit as st
import pandas as pd
import random
import time

# ==========================================
# 1. 데이터 구조 (리스트 & 딕셔너리)
# ==========================================
sectors = ["직선 고속구간", "급커브 헤어핀", "빗길 슬릭", "최종 결승 직선"]
parts = ["구동 모터", "고전압 배터리", "인버터/제어기"]

motors_spec = {
    "IPMSM (영구자석 동기모터)": {"accel": 1.00, "max_spd": 310, "heat": 1.00, "desc": "균형 잡힌 표준 레이싱 모터"},
    "IM (유도전동기)": {"accel": 0.92, "max_spd": 335, "heat": 0.78, "desc": "열에 강하고 직선 최고속도가 높음"},
    "AFPM (축방향 자속 모터)": {"accel": 1.22, "max_spd": 295, "heat": 1.25, "desc": "초반 가속 폭발적, 온도가 빨리 오름"}
}

batteries_spec = {
    "NCM 811 (고출력 리튬이온)": {"cap": 100.0, "drain": 1.00, "regen": 1.00, "heat_stab": 1.00, "desc": "고출력 방전에 유리한 표준 배터리"},
    "LFP (리튬인산철)": {"cap": 95.0, "drain": 0.95, "regen": 0.95, "heat_stab": 0.72, "desc": "열 안정성이 매우 뛰어나 과열 방지"},
    "Solid-State (전고체 배터리)": {"cap": 115.0, "drain": 0.85, "regen": 1.45, "heat_stab": 0.85, "desc": "대용량(115%) 및 회생제동 충전 효율 극대화"}
}

inverters_spec = {
    "Si-IGBT (표준 인버터)": {"power": 1.00, "heat_red": 1.00, "regen_boost": 1.00, "desc": "기본 스위칭 전력 제어기"},
    "SiC-MOSFET (실리콘카바이드)": {"power": 1.08, "heat_red": 0.70, "regen_boost": 1.25, "desc": "발열 약 30% 감소 및 회생 효율 상승"},
    "Dual-Inverter 800V": {"power": 1.22, "heat_red": 1.12, "regen_boost": 1.10, "desc": "800V 승압으로 최고 출력 +22%"}
}

# random 라이브러리용 실시간 주행 돌발 변수
random_events = [
    ("순풍이 불어 가속력이 상승합니다!", 4.0, -0.4, 0.2),
    ("노면 접지력이 최상 상태입니다!", 2.0, 0.0, 0.0),
    ("맞바람이 불어 공기저항이 증가합니다.", -4.0, 0.3, -0.3),
    ("앞차 난기류로 냉각 효율이 약간 떨어집니다.", -1.5, 0.6, -0.1),
    ("배터리 셀 밸런싱이 최적 상태로 유지됩니다.", 1.0, -0.2, 0.3)
]

# ==========================================
# 2. 게임 상태 초기화 및 실시간 조작 콜백 함수 (def)
# ==========================================
def init_game():
    st.session_state.is_racing = False
    st.session_state.finished = False
    st.session_state.distance = 0.0        # 총 1200m 트랙
    st.session_state.elapsed_time = 0.0    # 주행 시간(초)
    st.session_state.speed = 0.0           # 현재 속도(km/h)
    st.session_state.motor_temp = 45.0     # 모터 온도(℃)
    st.session_state.battery = 100.0       # 배터리 잔량(%)
    st.session_state.score = 100           # 레이싱 점수
    
    # 실시간 운전 조작 상태 (주행 중 버튼 클릭으로 즉시 변경됨)
    st.session_state.pedal = "ACCEL"       # ACCEL(풀악셀), REGEN(회생제동), BOOST(오버부스트), COAST(탄력주행)
    st.session_state.torque_limit = 100    # 100(풀파워) 또는 75(빗길 안전모드)
    st.session_state.cooling = 2           # 1(ECO), 2(NORMAL), 3(MAX)
    
    st.session_state.status_msg = "개러지에서 부품을 고른 뒤 '🏁 레이스 스타트!'를 누르면 차가 출발합니다!"
    st.session_state.event_msg = "실시간 텔레메트리 대기 중..."
    st.session_state.alert_level = "info"

# 버튼 클릭 시 딜레이 없이 즉시 조작 상태를 바꾸는 콜백 함수들
def start_race():
    st.session_state.is_racing = True
    st.session_state.finished = False
    st.session_state.battery = batteries_spec[st.session_state.selected_battery]["cap"]
    st.session_state.pedal = "ACCEL"
    st.session_state.status_msg = "🚦 출발! 트랙 구간 변화에 맞춰 페달과 냉각 시스템을 실시간 조작하세요!"

def set_pedal(mode):
    st.session_state.pedal = mode

def set_torque(val):
    st.session_state.torque_limit = val

def set_cooling(level):
    st.session_state.cooling = level

# ==========================================
# 3. 실시간 물리 엔진 업데이트 함수 (def + if-elif-else + random)
# ==========================================
def update_race_tick():
    m_spec = motors_spec[st.session_state.selected_motor]
    b_spec = batteries_spec[st.session_state.selected_battery]
    i_spec = inverters_spec[st.session_state.selected_inverter]
    
    dist = st.session_state.distance
    sec_idx = min(3, int(dist // 300))
    current_sector = sectors[sec_idx]
    
    pedal = st.session_state.pedal
    t_limit = st.session_state.torque_limit / 100.0
    cool_lv = st.session_state.cooling
    
    # 냉각 시스템 단계별 냉각량 및 배터리 소모량
    if cool_lv == 1:
        cool_effect, cool_drain = 0.35, 0.08
    elif cool_lv == 2:
        cool_effect, cool_drain = 0.95, 0.25
    else:
        cool_effect, cool_drain = 2.10, 0.65

    # random 라이브러리를 이용한 실시간 트랙 변수 적용
    if random.random() < 0.35:
        ev_text, ev_spd, ev_temp, ev_bat = random.choice(random_events)
        st.session_state.event_msg = ev_text
    else:
        ev_spd, ev_temp, ev_bat = 0.0, 0.0, 0.0

    spd = st.session_state.speed
    temp = st.session_state.motor_temp
    bat = st.session_state.battery
    score = st.session_state.score
    
    # 페달 조작에 따른 가속/감속/발열/충전 계산
    if pedal == "ACCEL":
        accel_force = 24.0 * t_limit * m_spec["accel"] * i_spec["power"]
        max_v = m_spec["max_spd"] * (0.85 + 0.15 * t_limit)
        spd = min(max_v, spd + accel_force - (spd * 0.045) + ev_spd)
        temp += (2.2 * t_limit * m_spec["heat"] * i_spec["heat_red"] * b_spec["heat_stab"]) - cool_effect + ev_temp
        bat -= (1.35 * t_limit * b_spec["drain"] + cool_drain) - ev_bat
        msg = f"⚡ 풀악셀 주행 중 (토크 상한 {st.session_state.torque_limit}%)"
        level = "info"
        
    elif pedal == "BOOST":
        accel_force = 35.0 * t_limit * m_spec["accel"] * i_spec["power"]
        max_v = m_spec["max_spd"] + 25
        spd = min(max_v, spd + accel_force - (spd * 0.04) + ev_spd)
        temp += (3.8 * t_limit * m_spec["heat"] * i_spec["heat_red"]) - cool_effect + ev_temp
        bat -= (2.45 * t_limit * b_spec["drain"] + cool_drain) - ev_bat
        msg = "🔥 오버부스트 가동! 인버터 최대 출력으로 폭발적 가속 중!"
        level = "warning"
        
    elif pedal == "REGEN":
        spd = max(75.0, spd - 26.0 + ev_spd)
        charge = 1.65 * b_spec["regen"] * i_spec["regen_boost"]
        temp += 0.4 - cool_effect + ev_temp
        bat += charge - cool_drain + ev_bat
        msg = f"🔋 회생제동 작동 중! 감속 에너지를 전기로 변환해 배터리 충전 (+{charge:.1f}%/틱)"
        level = "success"
        
    else:  # COAST (탄력주행)
        spd = max(60.0, spd - 8.0 + ev_spd)
        temp -= cool_effect
        bat -= cool_drain
        msg = "💨 탄력 주행(코스팅) 중 — 배터리 절약 및 모터 냉각"
        level = "info"

    # 3. 조건문 (if-elif-else): 트랙 구간별 공학 규칙 및 페널티 판정
    if current_sector == "급커브 헤어핀":
        if pedal == "REGEN":
            bat += 0.8  # 코너 회생제동 보너스
            msg = "🏁 헤어핀 코너 회생제동 성공! 안정적인 코너링 + 배터리 추가 회수!"
            level = "success"
        elif spd > 205:
            spd *= 0.82
            score = max(0, score - 3)
            msg = "⚠️ 헤어핀 과속 진입! 회생제동(🔋)을 눌러 감속하지 않으면 코너를 이탈합니다!"
            level = "error"
            
    elif current_sector == "빗길 슬릭":
        if pedal in ["ACCEL", "BOOST"] and st.session_state.torque_limit > 80:
            # random으로 빗길 휠스핀 발생
            if random.random() < 0.75:
                spd *= 0.76
                score = max(0, score - 3)
                msg = "⚠️ 빗길 휠스핀(슬립) 발생! 우측의 '🛡️ 빗길 안전모드(75%)'를 누르세요!"
                level = "error"
        else:
            msg = "✅ 빗길 트랙션 제어 안정적! 미끄러짐 없이 주행 중"
            level = "success"

    # 모터 과열(95℃ 이상) 출력 제한 판정
    temp = max(35.0, temp + random.uniform(-0.3, 0.4))
    if temp >= 95.0:
        spd *= 0.78
        score = max(0, score - 2)
        msg = "🔥 모터 과열 경고(95℃ 초과)! 출력 제한 발동! 냉각 시스템을 '3: MAX'로 올리세요!"
        level = "error"

    # 거리 및 시간 업데이트 (1틱 = 0.35초)
    dt = 0.35
    moved = (spd * 0.145) + random.uniform(-0.5, 0.5)
    st.session_state.distance = min(1200.0, dist + max(5.0, moved))
    st.session_state.elapsed_time = round(st.session_state.elapsed_time + dt, 2)
    st.session_state.speed = round(spd, 1)
    st.session_state.motor_temp = round(temp, 1)
    st.session_state.battery = round(max(0.0, min(b_spec["cap"], bat)), 1)
    st.session_state.score = score
    st.session_state.status_msg = msg
    st.session_state.alert_level = level

    # 완주 또는 방전 종료 조건 확인
    if st.session_state.battery <= 0:
        st.session_state.is_racing = False
        st.session_state.finished = True
        st.session_state.status_msg = "🪫 배터리 완전 방전(DNF)! 에너지 관리 실패로 주행이 중단되었습니다."
        st.session_state.alert_level = "error"
    elif st.session_state.distance >= 1200.0:
        st.session_state.is_racing = False
        st.session_state.finished = True
        st.session_state.status_msg = f"🏆 1,200m 완주 성공! 최종 기록: {st.session_state.elapsed_time}초 / 점수: {st.session_state.score}점"
        st.session_state.alert_level = "success"

# ==========================================
# 4. 실시간 레이싱 트랙 시각화 함수 (SVG 렌더링)
# ==========================================
def render_live_track(distance, speed, pedal, temp, cooling):
    progress_pct = min(94.0, (distance / 1200.0) * 90.0 + 3.0)
    
    # 차량 주위 이펙트 색상 (오버부스트=주황, 회생제동=초록, 최대냉각=하늘색)
    aura_color = "transparent"
    if pedal == "BOOST":
        aura_color = "#f97316"
    elif pedal == "REGEN":
        aura_color = "#22c55e"
    elif cooling == 3 or temp >= 85:
        aura_color = "#38bdf8"

    svg_html = f"""
<div style="background:#0f172a; border-radius:12px; padding:12px; border:2px solid #334155; margin-bottom:10px;">
<svg width="100%" height="135" viewBox="0 0 800 135">
  <!-- 4개 트랙 구간 배경 -->
  <rect x="0" y="25" width="200" height="80" fill="#1e293b" />
  <rect x="200" y="25" width="200" height="80" fill="#3b2f1e" />
  <rect x="400" y="25" width="200" height="80" fill="#172a45" />
  <rect x="600" y="25" width="200" height="80" fill="#1e293b" />
  
  <!-- 구간 경계선 및 텍스트 -->
  <line x1="200" y1="25" x2="200" y2="105" stroke="#f59e0b" stroke-width="2" stroke-dasharray="5,5"/>
  <line x1="400" y1="25" x2="400" y2="105" stroke="#38bdf8" stroke-width="2" stroke-dasharray="5,5"/>
  <line x1="600" y1="25" x2="600" y2="105" stroke="#22c55e" stroke-width="2" stroke-dasharray="5,5"/>
  <line x1="775" y1="25" x2="775" y2="105" stroke="#ffffff" stroke-width="5" stroke-dasharray="6,6"/>

  <text x="100" y="17" fill="#94a3b8" font-size="12" text-anchor="middle" font-weight="bold">① 직선 고속 (0~300m)</text>
  <text x="300" y="17" fill="#fbbf24" font-size="12" text-anchor="middle" font-weight="bold">② 급커브 헤어핀 (회생제동!)</text>
  <text x="500" y="17" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="bold">③ 빗길 슬릭 (토크 75% 제한!)</text>
  <text x="700" y="17" fill="#4ade80" font-size="12" text-anchor="middle" font-weight="bold">④ 결승 직선 (부스트!)</text>

  <!-- 중앙 차선 -->
  <line x1="0" y1="65" x2="800" y2="65" stroke="#64748b" stroke-width="2" stroke-dasharray="14,14"/>
  
  <!-- 내 전기차(EV) 위치 및 이펙트 -->
  <g transform="translate({progress_pct * 7.6}, 46)">
    <rect x="-8" y="-6" width="62" height="48" rx="12" fill="{aura_color}" opacity="0.35"/>
    <rect x="0" y="2" width="46" height="32" rx="8" fill="#0ea5e9" stroke="#e0f2fe" stroke-width="2"/>
    <rect x="12" y="6" width="18" height="24" rx="4" fill="#0f172a"/>
    <text x="23" y="50" fill="#ffffff" font-size="11" text-anchor="middle" font-weight="bold">{int(speed)} km/h</text>
  </g>
</svg>
</div>
"""
    st.markdown(svg_html, unsafe_allow_html=True)

# ==========================================
# 5. 메인 화면 UI 구성
# ==========================================
st.set_page_config(page_title="하이퍼 EV 레이싱: 실시간 주행", page_icon="🏎️", layout="wide")

if "is_racing" not in st.session_state:
    init_game()

# 레이스 진행 중이면 물리 엔진 1틱 업데이트
if st.session_state.is_racing and not st.session_state.finished:
    update_race_tick()

st.title("🏎️⚡ 하이퍼 EV 레이싱: 파워트레인 마스터 (실시간 주행판)")

# [1] 개러지 부품 선택 (주행 시작 시 자동 잠금)
lock_status = "🔒 LOCKED (주행 중 교체 불가)" if (st.session_state.is_racing or st.session_state.finished) else "🔓 OPEN (출발 전 부품 세팅)"
st.caption(f"🛠️ **개러지 파워트레인 세팅:** `{lock_status}`")

g1, g2, g3 = st.columns(3)
disabled_flag = st.session_state.is_racing or st.session_state.finished
with g1:
    st.selectbox("구동 모터", list(motors_spec.keys()), key="selected_motor", disabled=disabled_flag)
with g2:
    st.selectbox("고전압 배터리", list(batteries_spec.keys()), key="selected_battery", disabled=disabled_flag)
with g3:
    st.selectbox("인버터 제어기", list(inverters_spec.keys()), key="selected_inverter", disabled=disabled_flag)

# [2] 트랙 구간별 엔지니어 전략 무전 가이드
dist = st.session_state.distance
if st.session_state.motor_temp >= 86:
    st.error("🚨 [엔지니어 긴급 무전] 모터 온도 86℃ 돌파! 지금 즉시 우측에서 '❄️ 3: MAX 냉각'을 누르세요!")
elif dist < 300:
    st.info("📡 [구간 가이드 ① 직선 고속] '⚡ 풀악셀' 또는 '🔥 오버부스트'로 속도를 최대로 끌어올리세요!")
elif dist < 600:
    st.warning("📡 [구간 가이드 ② 급커브 헤어핀] 코너 진입! 지금 '🔋 회생제동' 버튼을 눌러 감속하고 배터리를 충전하세요!")
elif dist < 900:
    st.warning("📡 [구간 가이드 ③ 빗길 슬릭] 노면이 미끄럽습니다! 우측의 '🛡️ 빗길 안전모드(75%)'를 눌러 휠스핀을 막으세요!")
else:
    st.success("📡 [구간 가이드 ④ 최종 결승 직선] 마지막 스퍼트! '⚡ 100% 풀파워' + '🔥 오버부스트'로 결승선을 통과하세요!")

# [3] 실시간 이동 트랙 화면 (SVG)
render_live_track(
    st.session_state.distance,
    st.session_state.speed,
    st.session_state.pedal,
    st.session_state.motor_temp,
    st.session_state.cooling
)

# [4] 실시간 운전 조작 패널 (페달 + ECU 버튼)
ctrl_col, status_col = st.columns([1.15, 1.0])

with ctrl_col:
    st.subheader("🎮 실시간 운전석 컨트롤 (주행 중 즉시 반응)")
    
    # 시작 / 리셋 버튼
    top_b1, top_b2 = st.columns(2)
    with top_b1:
        st.button(
            "🏁 레이스 스타트! (실시간 주행 시작)",
            on_click=start_race,
            type="primary",
            disabled=disabled_flag,
            use_container_width=True
        )
    with top_b2:
        st.button("🔄 개러지로 복귀 (리셋)", on_click=init_game, use_container_width=True)

    st.markdown("**1️⃣ 주행 페달 조작 (클릭 시 즉시 전환)**")
    p1, p2, p3, p4 = st.columns(4)
    p1.button("⚡ 풀악셀", on_click=set_pedal, args=("ACCEL",), use_container_width=True)
    p2.button("🔋 회생제동", on_click=set_pedal, args=("REGEN",), use_container_width=True)
    p3.button("🔥 오버부스트", on_click=set_pedal, args=("BOOST",), use_container_width=True)
    p4.button("💨 탄력주행", on_click=set_pedal, args=("COAST",), use_container_width=True)

    st.markdown("**2️⃣ 인버터 토크 상한 (빗길 슬립 제어)**")
    t1, t2 = st.columns(2)
    t1.button("🚀 100% 풀파워 모드", on_click=set_torque, args=(100,), use_container_width=True)
    t2.button("🛡️ 75% 빗길 안전모드", on_click=set_torque, args=(75,), use_container_width=True)

    st.markdown("**3️⃣ 냉각 시스템 출력 (모터 과열 방지)**")
    c1, c2, c3 = st.columns(3)
    c1.button("❄️ 1: ECO (절전)", on_click=set_cooling, args=(1,), use_container_width=True)
    c2.button("❄️ 2: NORMAL", on_click=set_cooling, args=(2,), use_container_width=True)
    c3.button("❄️ 3: MAX (최대냉각)", on_click=set_cooling, args=(3,), use_container_width=True)
    
    with st.expander("💡 냉각 시스템이 뭔가요?"):
        st.write("전기모터를 강하게 돌리면 전류 때문에 열이 발생합니다. **95℃**가 넘으면 출력이 강제로 줄어드므로, 온도가 오르면 **3: MAX**를 눌러 냉각 팬과 펌프를 최대로 돌려 식혀주세요! (단, 냉각기를 강하게 돌리면 배터리가 조금 더 빨리 닳습니다.)")

with status_col:
    st.subheader("📊 실시간 계기판 & 전장 부품 진단")
    
    if st.session_state.alert_level == "error":
        st.error(st.session_state.status_msg)
    elif st.session_state.alert_level == "warning":
        st.warning(st.session_state.status_msg)
    elif st.session_state.alert_level == "success":
        st.success(st.session_state.status_msg)
    else:
        st.info(st.session_state.status_msg)
        
    st.caption(f"🎲 **실시간 트랙 변수 (random):** {st.session_state.event_msg}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⏱️ 랩타임", f"{st.session_state.elapsed_time}초")
    m2.metric("📏 주행거리", f"{int(st.session_state.distance)}m")
    m3.metric("🌡️ 모터온도", f"{st.session_state.motor_temp}℃")
    m4.metric("🏆 점수", f"{st.session_state.score}점")

    # 4. 반복문 (for): 전장 부품 리스트를 순회하며 상태 테이블 생성
    diag_rows = []
    for part in parts:
        if part == "구동 모터":
            load_s = f"{st.session_state.torque_limit}%"
            vt_s = f"{st.session_state.motor_temp}℃"
            st_s = "🔥 과열주의" if st.session_state.motor_temp >= 88 else ("⚡ 고출력" if st.session_state.pedal in ["ACCEL", "BOOST"] else "✅ 정상")
        elif part == "고전압 배터리":
            load_s = f"{st.session_state.battery}%"
            volt = random.randint(355, 370) if st.session_state.battery < 20 else random.randint(396, 405)
            if "800V" in st.session_state.selected_inverter:
                volt *= 2
            vt_s = f"{volt}V"
            st_s = "🔋 회생충전" if st.session_state.pedal == "REGEN" else ("🪫 저전압" if st.session_state.battery < 20 else "✅ 정상")
        elif part == "인버터/제어기":
            cool_names = {1: "ECO", 2: "NORMAL", 3: "MAX"}
            load_s = f"냉각 {cool_names[st.session_state.cooling]}"
            vt_s = "정상"
            st_s = "❄️ 최대냉각" if st.session_state.cooling == 3 else "✅ 안정"
            
        diag_rows.append({"전장 부품": part, "부하/효율": load_s, "온도/전압": vt_s, "주행 상태": st_s})
        
    st.table(pd.DataFrame(diag_rows))

# ==========================================
# 6. 실시간 자동 주행 루프 (0.35초마다 화면 자동 갱신)
# ==========================================
if st.session_state.is_racing and not st.session_state.finished:
    time.sleep(0.35)
    st.rerun()
