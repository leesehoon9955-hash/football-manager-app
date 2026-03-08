
import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import json
import re
import uuid
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import platform
import google.generativeai as genai
from utils import generate_dummy_players, unflatten_dict

# .env 파일에서 환경 변수 로드
load_dotenv()

# Google Gemini API 초기화 (Streamlit Secrets 우선, 없으면 환경변수)
try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    gemini_key = os.getenv("GEMINI_API_KEY")

if gemini_key:
    genai.configure(api_key=gemini_key)

# --- 상수 및 설정 ---
PLAYERS_FILE = "players.json"
MATCHES_FILE = "matches.json"

# Matplotlib 한글 폰트 설정 (OS별 처리)
if platform.system() == 'Windows':
    plt.rc('font', family='Malgun Gothic')
elif platform.system() == 'Darwin': # Mac
    plt.rc('font', family='AppleGothic')
else: # Linux
    plt.rc('font', family='NanumGothic')
plt.rcParams['axes.unicode_minus'] = False

# 화면에 표시할 기본 정보 컬럼 (한글명)
BASE_COLUMNS = ['이름', '나이', '주 포지션']

# 선수 편집 옵션
PREFERRED_FOOT_OPTIONS = ['오른발', '왼발', '양발']
POSITION_OPTIONS = [
    'GK', 'SW', 'CB', 'LB', 'RB', 'LWB', 'RWB', 'DM', 'CM', 'LM', 'RM', 'AM', 'LW', 'RW', 'SS', 'CF', 'ST'
]
ATTRIBUTE_OPTIONS = list(range(1, 21))

COLUMN_CONFIG = {
    # Player Info
    "player_info.name": st.column_config.TextColumn("이름", help="선수 이름"),
    "player_info.age": st.column_config.NumberColumn("나이", format="%d세"),
    "player_info.preferred_foot": st.column_config.SelectboxColumn("주 사용 발", options=PREFERRED_FOOT_OPTIONS),
    "player_info.main_position": st.column_config.SelectboxColumn("주 포지션", options=POSITION_OPTIONS),
    "player_info.sub_positions": st.column_config.TextColumn("서브 포지션", help=f"쉼표로 구분하여 입력 ({', '.join(POSITION_OPTIONS)})"),
    "player_info.total_apps": st.column_config.NumberColumn("총 출전 수", format="%d회"),
    "player_info.average_rating": st.column_config.NumberColumn("평균 평점", format="%.2f"),
    # Status
    "status.condition": st.column_config.NumberColumn("컨디션", help="1~5점, 높을수록 좋음", min_value=1, max_value=5),
    "status.injury_risk": st.column_config.TextColumn("부상 위험"),
    # Technical Attributes
    "attributes.technical.dribbling": st.column_config.SelectboxColumn("드리블", options=ATTRIBUTE_OPTIONS),
    "attributes.technical.man_marking": st.column_config.SelectboxColumn("대인 마크", options=ATTRIBUTE_OPTIONS),
    "attributes.technical.passing": st.column_config.SelectboxColumn("패스", options=ATTRIBUTE_OPTIONS),
    "attributes.technical.shooting": st.column_config.SelectboxColumn("슈팅", options=ATTRIBUTE_OPTIONS),
    "attributes.technical.tackling": st.column_config.SelectboxColumn("태클", options=ATTRIBUTE_OPTIONS),
    "attributes.technical.first_touch": st.column_config.SelectboxColumn("퍼스트 터치", options=ATTRIBUTE_OPTIONS),
    "attributes.technical.crossing": st.column_config.SelectboxColumn("크로스", options=ATTRIBUTE_OPTIONS),
    "attributes.technical.heading": st.column_config.SelectboxColumn("헤딩", options=ATTRIBUTE_OPTIONS),
    # Mental Attributes
    "attributes.mental.aggression": st.column_config.SelectboxColumn("적극성", options=ATTRIBUTE_OPTIONS),
    "attributes.mental.anticipation": st.column_config.SelectboxColumn("예측력", options=ATTRIBUTE_OPTIONS),
    "attributes.mental.composure": st.column_config.SelectboxColumn("침착성", options=ATTRIBUTE_OPTIONS),
    "attributes.mental.concentration": st.column_config.SelectboxColumn("집중력", options=ATTRIBUTE_OPTIONS),
    "attributes.mental.decisions": st.column_config.SelectboxColumn("판단력", options=ATTRIBUTE_OPTIONS),
    "attributes.mental.teamwork": st.column_config.SelectboxColumn("팀워크", options=ATTRIBUTE_OPTIONS),
    "attributes.mental.vision": st.column_config.SelectboxColumn("시야", options=ATTRIBUTE_OPTIONS),
    "attributes.mental.positioning": st.column_config.SelectboxColumn("위치 선정", options=ATTRIBUTE_OPTIONS),
    # Physical Attributes
    "attributes.physical.acceleration": st.column_config.SelectboxColumn("순간 속도", options=ATTRIBUTE_OPTIONS),
    "attributes.physical.pace": st.column_config.SelectboxColumn("주력", options=ATTRIBUTE_OPTIONS),
    "attributes.physical.stamina": st.column_config.SelectboxColumn("지구력", options=ATTRIBUTE_OPTIONS),
    "attributes.physical.strength": st.column_config.SelectboxColumn("몸싸움", options=ATTRIBUTE_OPTIONS),
    "attributes.physical.agility": st.column_config.SelectboxColumn("민첩성", options=ATTRIBUTE_OPTIONS),
    "attributes.physical.jumping_reach": st.column_config.SelectboxColumn("점프력", options=ATTRIBUTE_OPTIONS),
    "attributes.physical.natural_fitness": st.column_config.SelectboxColumn("체력", options=ATTRIBUTE_OPTIONS),
    # Hidden ID
    "id": None
}


# --- Firebase 연동 함수 ---
def initialize_firebase():
    """환경 변수 또는 Streamlit Secrets를 사용하여 Firebase 앱을 초기화합니다."""
    if firebase_admin._apps:
        return True
    try:
        # 1. Streamlit Cloud 배포 환경 (Secrets 사용)
        try:
            if "firebase" in st.secrets:
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                return True
        except Exception:
            pass

        # 2. 로컬 개발 환경 (.env 사용)
        cred_path = os.getenv("FIREBASE_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            return True
        return False
    except Exception as e:
        st.error(f"😥 Firebase 연결 실패: {e}")
        return False

def fetch_players_from_firestore():
    """Firestore 'players' 컬렉션에서 모든 선수 데이터를 가져옵니다."""
    if not firebase_admin._apps: return None
    try:
        db = firestore.client()
        docs = db.collection('players').stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        st.error(f"Firestore 데이터 로드 실패: {e}")
        return None

def upload_players_to_firestore(players_list):
    """선수 목록을 Firestore 'players' 컬렉션에 업로드합니다."""
    if not firebase_admin._apps: return False
    try:
        db = firestore.client()
        batch = db.batch()
        players_ref = db.collection('players')
        
        # 기존 데이터 삭제
        for doc in players_ref.stream(): batch.delete(doc.reference)
        
        # 새 데이터 추가
        for player in players_list:
            if player.get("player_info", {}).get("name"):
                doc_ref = players_ref.document(player["player_info"]["name"])
                batch.set(doc_ref, player)
        
        batch.commit()
        return True
    except Exception as e:
        st.error(f"Firestore 업로드 실패: {e}")
        return False

# --- 데이터 관리 함수 ---
def load_players_data(from_firestore=False):
    """Firestore 또는 로컬 파일에서 선수 데이터를 로드하고 flatten 합니다."""
    players_data = None
    if from_firestore and firebase_admin._apps:
        with st.spinner("Firestore에서 데이터를 가져오는 중..."):
            players_data = fetch_players_from_firestore()
            if players_data is not None:
                with open(PLAYERS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(players_data, f, ensure_ascii=False, indent=4)
                st.toast("Firestore 데이터를 성공적으로 가져왔습니다.")

    if players_data is None:
        try:
            with open(PLAYERS_FILE, 'r', encoding='utf-8') as f: players_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            players_data = []

    for p in players_data:
        if "id" not in p or not p["id"]: p["id"] = str(uuid.uuid4())

    df = pd.json_normalize(players_data, sep='.')
    
    # 컬럼 순서 보장을 위해 모든 컬럼이 항상 존재하도록 처리
    expected_columns = [col for col in COLUMN_CONFIG.keys() if col != 'id']
    for col in expected_columns:
        if col not in df.columns:
            df[col] = pd.NA

    # sub_positions 리스트를 문자열로 변환 (에러 수정)
    if 'player_info.sub_positions' in df.columns:
        df['player_info.sub_positions'] = df['player_info.sub_positions'].apply(
            lambda x: ', '.join(map(str, x)) if isinstance(x, list) else x
        )
    
    return df

def save_players_data(df: pd.DataFrame):
    """Flatten 된 DataFrame을 nested JSON으로 변환하여 로컬 및 Firestore에 저장합니다."""
    df_clean = df.dropna(subset=['player_info.name'], how='all').copy()
    df_clean['id'] = df_clean.apply(lambda row: row.get('id') or str(uuid.uuid4()), axis=1)

    # sub_positions 문자열을 리스트로 변환 (에러 수정)
    if 'player_info.sub_positions' in df_clean.columns:
        df_clean['player_info.sub_positions'] = df_clean['player_info.sub_positions'].apply(
            lambda x: [item.strip() for item in x.split(',')] if isinstance(x, str) else x
        )

    players_list_flat = df_clean.to_dict('records')
    players_list_nested = [unflatten_dict(p) for p in players_list_flat]

    # 로컬 파일 저장
    with open(PLAYERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(players_list_nested, f, ensure_ascii=False, indent=4)
    st.success("✅ 로컬 파일 저장 완료!")
    
    # Firestore 업로드
    if firebase_admin._apps:
        with st.spinner('Firestore에 데이터를 동기화하는 중...'):
            if upload_players_to_firestore(players_list_nested):
                st.success("🔥 Firestore 동기화 완료!")
            else:
                st.error("❌ Firestore 동기화 실패.")
    else:
        st.warning("Firebase가 연결되지 않아 로컬에만 저장되었습니다.")


def fetch_matches_from_firestore():
    """Firestore 'matches' 컬렉션에서 모든 경기 데이터를 가져옵니다."""
    if not firebase_admin._apps: return None
    try:
        db = firestore.client()
        docs = db.collection('matches').stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        st.error(f"Firestore 경기 데이터 로드 실패: {e}")
        return None

def upload_matches_to_firestore(matches_list):
    """경기 목록을 Firestore 'matches' 컬렉션에 업로드합니다."""
    if not firebase_admin._apps: return False
    try:
        db = firestore.client()
        batch = db.batch()
        matches_ref = db.collection('matches')

        # 기존 데이터와 동기화를 위해 모든 문서를 확인하며 업데이트/추가/삭제를 결정할 수 있지만,
        # 여기서는 간단하게 전체를 덮어쓰는 방식을 사용합니다.
        # 기존 데이터 삭제
        for doc in matches_ref.stream():
            batch.delete(doc.reference)

        # 새 데이터 추가
        for match in matches_list:
            if match.get("id"):
                doc_ref = matches_ref.document(match["id"])
                batch.set(doc_ref, match)

        batch.commit()
        return True
    except Exception as e:
        st.error(f"Firestore 경기 데이터 업로드 실패: {e}")
        return False

def load_matches_data(from_firestore=False):
    """Firestore 또는 로컬 파일에서 경기 데이터를 로드합니다."""
    matches_data = None
    if from_firestore and firebase_admin._apps:
        with st.spinner("Firestore에서 경기 데이터를 가져오는 중..."):
            matches_data = fetch_matches_from_firestore()
            if matches_data is not None:
                with open(MATCHES_FILE, 'w', encoding='utf-8') as f:
                    json.dump(matches_data, f, ensure_ascii=False, indent=4)
                st.toast("Firestore 경기 데이터를 성공적으로 가져왔습니다.")

    if matches_data is None:
        try:
            with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
                matches_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            matches_data = []
    
    for m in matches_data:
        if "id" not in m or not m["id"]: m["id"] = str(uuid.uuid4())

    # 날짜 순으로 정렬
    if matches_data:
        matches_data = sorted(matches_data, key=lambda x: x.get('date', ''), reverse=True)

    return matches_data

def save_matches_data(matches_list):
    """경기 목록을 로컬 및 Firestore에 저장합니다."""
    # 날짜 순으로 정렬
    if matches_list:
        matches_list = sorted(matches_list, key=lambda x: x.get('date', ''), reverse=True)
        
    # 로컬 파일 저장
    with open(MATCHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches_list, f, ensure_ascii=False, indent=4)
    st.success("✅ 로컬에 경기 정보 저장 완료!")

    # Firestore 업로드
    if firebase_admin._apps:
        with st.spinner('Firestore에 경기 정보를 동기화하는 중...'):
            if upload_matches_to_firestore(matches_list):
                st.success("🔥 Firestore 경기 정보 동기화 완료!")
            else:
                st.error("❌ Firestore 경기 정보 동기화 실패.")

def draw_pitch(formation, gk_name, field_players, all_players_df=None, opt_mapping=None):
    """쿼터별 포메이션 이미지를 생성합니다."""
    import matplotlib.patheffects as patheffects
    
    # 모바일 환경에 맞게 크기 축소
    fig, ax = plt.subplots(figsize=(4, 5.5), dpi=100)
    
    # 축구장 배경 (교차하는 투톤 잔디 패턴)
    ax.set_facecolor('#4CAF50')
    for i in range(11):
        color = '#4CAF50' if i % 2 == 0 else '#43A047'
        ax.add_patch(patches.Rectangle((-5, i*10 - 5), 110, 10, facecolor=color, edgecolor='none', zorder=0))

    # 경기장 라인 그리기
    plt.plot([0, 100, 100, 0, 0], [0, 0, 100, 100, 0], color='white', linewidth=2, zorder=1)
    plt.plot([0, 100], [50, 50], color='white', linewidth=1.5, zorder=1)  # 하프라인
    circle = patches.Circle((50, 50), 10, edgecolor='white', facecolor='none', linewidth=1.5, zorder=1)
    ax.add_patch(circle)
    center_dot = patches.Circle((50, 50), 0.5, facecolor='white', zorder=1)
    ax.add_patch(center_dot)
    
    # 페널티 박스 (하단, 상단)
    plt.plot([20, 20, 80, 80], [0, 18, 18, 0], color='white', linewidth=1.5, zorder=1)
    plt.plot([20, 20, 80, 80], [100, 82, 82, 100], color='white', linewidth=1.5, zorder=1)
    
    # 골 에어리어
    plt.plot([35, 35, 65, 65], [0, 6, 6, 0], color='white', linewidth=1.5, zorder=1)
    plt.plot([35, 35, 65, 65], [100, 94, 94, 100], color='white', linewidth=1.5, zorder=1)

    # 페널티 아크 (대략적인 표현)
    arc_bottom = patches.Arc((50, 18), 15, 10, theta1=0, theta2=180, edgecolor='white', linewidth=1.5, zorder=1)
    ax.add_patch(arc_bottom)
    arc_top = patches.Arc((50, 82), 15, 10, theta1=180, theta2=360, edgecolor='white', linewidth=1.5, zorder=1)
    ax.add_patch(arc_top)

    # 포메이션별 고정 포지션 및 좌표 정의 (수비부터 공격 순)
    formations = {
        "4-4-2": [
            (15, 18, 'LB'), (38, 15, 'CB'), (62, 15, 'CB'), (85, 18, 'RB'),
            (20, 45, 'LM'), (40, 42, 'CM'), (60, 42, 'CM'), (80, 45, 'RM'),
            (35, 75, 'CF'), (65, 75, 'ST')
        ],
        "4-3-3": [
            (15, 18, 'LB'), (38, 15, 'CB'), (62, 15, 'CB'), (85, 18, 'RB'),
            (30, 40, 'CM'), (50, 38, 'CM'), (70, 40, 'CM'),
            (25, 75, 'LW'), (50, 80, 'ST'), (75, 75, 'RW')
        ],
        "3-5-2": [
            (25, 15, 'CB'), (50, 15, 'CB'), (75, 15, 'CB'),
            (15, 45, 'LWB'), (35, 40, 'CM'), (50, 38, 'CM'), (65, 40, 'CM'), (85, 45, 'RWB'),
            (35, 75, 'CF'), (65, 75, 'ST')
        ]
    }

    def get_position_category(pos):
        if pos in ['SW', 'CB', 'LB', 'RB', 'LWB', 'RWB']: return 'DEF'
        elif pos in ['DM', 'CM', 'LM', 'RM', 'AM']: return 'MID'
        elif pos in ['LW', 'RW', 'SS', 'CF', 'ST']: return 'FWD'
        return 'MID'

    def get_position_color(pos):
        cat = get_position_category(pos)
        if cat == 'FWD': return '#E53935' # 빨강
        elif cat == 'MID': return '#1E88E5' # 파랑
        elif cat == 'DEF': return '#43A047' # 초록
        return '#757575'

    # 해당 포메이션 좌표 가져오기
    coords = formations.get(formation, formations["4-4-2"])

    # 스타일 설정
    path_eff = [patheffects.withStroke(linewidth=2, foreground='w')]

    # 선수 배정 로직 (AI 매핑 최우선)
    available_slots = list(coords)
    assigned_players = []
    unassigned_players = []
    
    if opt_mapping is None:
        opt_mapping = {}

    # 1. AI가 할당한 정확한 포지션 슬롯 매칭
    for name in field_players:
        pos = opt_mapping.get(name, "UNKNOWN")
        matched = False
        for i, slot in enumerate(available_slots):
            if slot[2] == pos:
                assigned_players.append((slot[0], slot[1], slot[2], name))
                available_slots.pop(i)
                matched = True
                break
        if not matched:
            unassigned_players.append(name)
            
    # 2. 남은 선수들을 남은 슬롯에 순차 배정
    for name in unassigned_players:
        if available_slots:
            slot = available_slots.pop(0)
            assigned_players.append((slot[0], slot[1], slot[2], name))

    # 필드 플레이어 그리기
    for x, y, pos_name, name in assigned_players:
        color = get_position_color(pos_name)
        
        # 선수 위치 원
        p_circle = patches.Circle((x, y), 6, edgecolor='white', facecolor=color, linewidth=1.5, zorder=3)
        ax.add_patch(p_circle)
        
        # 포지션 텍스트 (원 안)
        ax.text(x, y, pos_name, ha='center', va='center', color='white', fontweight='bold', fontsize=8, zorder=4)
        # 선수 이름 텍스트 (원 위)
        txt = ax.text(x, y + 9, name, ha='center', va='center', color='black', fontweight='bold', fontsize=10, zorder=4)
        txt.set_path_effects(path_eff)

    # GK 배치
    gk_circle = patches.Circle((50, 5), 6, edgecolor='white', facecolor='#FB8C00', linewidth=1.5, zorder=3)
    ax.add_patch(gk_circle)
    ax.text(50, 5, 'GK', ha='center', va='center', color='white', fontweight='bold', fontsize=8, zorder=4)
    txt_gk = ax.text(50, 5 + 9, gk_name, ha='center', va='center', color='black', fontweight='bold', fontsize=10, zorder=4)
    txt_gk.set_path_effects(path_eff)

    ax.set_xlim(-2, 102)
    ax.set_ylim(-2, 102)
    ax.axis('off')
    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02) # 여백 최소화
    return fig

# --- UI 구성 ---
st.set_page_config(layout="wide")

with st.sidebar:
    st.title("⚽ FMS v2.0")
    firebase_initialized = initialize_firebase()
    if firebase_initialized: st.sidebar.success("🔥 Firebase 연결됨")
    else: st.sidebar.warning("🚨 Firebase 연결 안됨")
    
    selected_menu = st.radio("메뉴", ('선수 명단 관리', '선수 평가', 'AI 라인업 생성', '경기 목록', '경기 결과 기록'))
    st.info("선수 명단 수정 후 '변경사항 저장' 버튼을 눌러주세요.")

st.header(f"📊 {selected_menu}")

if selected_menu == '선수 명단 관리':
    st.write("선수 명단을 편집하고 '변경사항 저장' 버튼을 클릭하여 동기화하세요.")

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 Firebase와 동기화"):
            load_players_data(from_firestore=True)
            st.rerun()
    with col2:
        if st.button("👥 테스트 선수 15명 생성", help="15명의 임시 선수를 생성하여 덮어씁니다."):
            dummy_data = generate_dummy_players()
            dummy_df = pd.json_normalize(dummy_data, sep='.')
            save_players_data(dummy_df)
            st.rerun()

    players_df = load_players_data(from_firestore=st.session_state.get('first_load', True))
    if 'first_load' in st.session_state: del st.session_state['first_load']

    with st.expander("📤 일괄 데이터 편집 (엑셀/CSV)"):
        st.write("현재 명단 서식을 다운로드하여 엑셀에서 편집한 후, 다시 업로드하면 전체 업데이트가 진행됩니다.")
        
        @st.cache_data
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8-sig') # 한글 깨짐 방지용 utf-8-sig
            
        csv_data = convert_df(players_df)
        st.download_button(
            label="⬇️ 현재 명단 템플릿 다운로드 (CSV)",
            data=csv_data,
            file_name="players_template.csv",
            mime="text/csv",
        )
        
        uploaded_file = st.file_uploader("수정한 명단 파일 업로드 (.xlsx 또는 .csv)", type=["xlsx", "csv"])
        
        if uploaded_file is not None:
            if st.button("⬆️ 업로드된 데이터로 현재 명단 덮어쓰기", type="primary"):
                try:
                    with st.spinner("파일을 읽고 저장하는 중..."):
                        if uploaded_file.name.endswith('.csv'):
                            new_df = pd.read_csv(uploaded_file)
                        else:
                            new_df = pd.read_excel(uploaded_file)
                        save_players_data(new_df)
                    st.success("명단이 성공적으로 업데이트되었습니다! 화면을 리프레시합니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"엑셀 파일 처리 중 오류가 발생했습니다: {e}")

    # '선수 명단 관리'에서 보여주지 않을 컬럼 정의
    COLS_TO_HIDE_IN_EDITOR = [
        'player_info.total_apps', 
        'player_info.average_rating', 
        'status.condition', 
        'status.injury_risk'
    ]
    
    # 컬럼 순서 재정렬: BASE_COLUMNS를 앞으로, 나머지는 COLUMN_CONFIG 순서대로
    english_base_columns = [key for key, config in COLUMN_CONFIG.items() if config and hasattr(config, 'label') and config.label in BASE_COLUMNS]
    other_columns = [key for key in COLUMN_CONFIG.keys() if key != 'id' and key not in english_base_columns and key not in COLS_TO_HIDE_IN_EDITOR]
    
    # DataFrame에 존재하는 컬럼만 필터링하여 최종 순서 결정
    potential_order = english_base_columns + other_columns
    ordered_columns = [col for col in potential_order if col in players_df.columns]
    # 편집기에서는 숨겨진 컬럼 및 예외 컬럼을 추가하지 않음


    edited_df = st.data_editor(
        players_df,
        column_order=ordered_columns,
        num_rows="dynamic",
        key="player_editor",
        column_config=COLUMN_CONFIG
    )

    if st.button("💾 변경사항 저장", type="primary"):
        save_players_data(edited_df)
        st.rerun()

elif selected_menu == '선수 평가':
    st.subheader("📊 선수 종합 스탯")
    st.write("선수들의 경기 기록을 바탕으로 산출된 주요 스탯입니다.")

    players_df = load_players_data()
    
    if players_df.empty:
        st.warning("선수 데이터가 없습니다. '선수 명단 관리'에서 선수를 추가해주세요.")
    else:
        stats_df = players_df[[
            'player_info.name',
            'player_info.total_apps',
            'player_info.average_rating'
        ]].copy()
        
        # 컬럼명 변경
        stats_df.columns = ['이름', '총 출전 수', '평균 평점']
        
        # NaN 값을 0 또는 'N/A'로 처리
        stats_df['총 출전 수'] = stats_df['총 출전 수'].fillna(0).astype(int)
        stats_df['평균 평점'] = stats_df['평균 평점'].fillna(0).map('{:.2f}'.format)

        st.dataframe(
            stats_df.sort_values(by='평균 평점', ascending=False).reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )
    
    # 상세 매치 히스토리
    st.write("---")
    st.subheader("⚽ 선수별 매치 히스토리")

    if players_df.empty:
        st.warning("선수가 없어 매치 히스토리를 조회할 수 없습니다.")
    else:
        player_name_to_id = pd.Series(players_df['id'].values, index=players_df['player_info.name']).to_dict()
        player_names = players_df['player_info.name'].tolist()
        
        selected_player_name = st.selectbox("매치 히스토리를 조회할 선수를 선택하세요", options=player_names)

        if selected_player_name:
            player_id = player_name_to_id.get(selected_player_name)
            matches = load_matches_data()
            
            player_matches = []
            for m in matches:
                # 경기 결과가 있고, 선수가 라인업에 포함된 경우
                if m.get('status') == 'completed' and player_id in m.get('lineup', []):
                    res = m.get('result', {})
                    ratings = res.get('ratings', {})
                    player_rating = ratings.get(player_id, 'N/A')
                    
                    player_matches.append({
                        "날짜": m.get('date'),
                        "상대": m.get('opponent'),
                        "결과": f"{res.get('home_score', '-')} : {res.get('away_score', '-')}",
                        "평점": f"{player_rating:.1f}" if isinstance(player_rating, float) else player_rating
                    })
            
            if not player_matches:
                st.info(f"'{selected_player_name}' 선수는 아직 출전 기록이 없습니다.")
            else:
                history_df = pd.DataFrame(player_matches)
                st.dataframe(history_df.sort_values(by='날짜', ascending=False), use_container_width=True, hide_index=True)

elif selected_menu == 'AI 라인업 생성':
    st.subheader("🤖 AI 쿼터별 라인업 배정")
    st.write("strategy.md 전략 파일에 기반하여 최적의 로테이션을 생성합니다.")

    all_players_df = load_players_data()
    if all_players_df.empty:
        st.warning("선수 데이터가 없습니다.")
    else:
        player_names = all_players_df['player_info.name'].tolist()
        
        # 1. 경기 설정 입력
        with st.expander("⚙️ 경기 및 전략 설정", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                match_quarters = st.number_input("경기 쿼터 수", min_value=1, value=5, step=1)
                formation = st.selectbox("선호 포메이션", ["4-4-2", "4-3-3", "3-5-2"])
            with col2:
                max_quarters = st.number_input("인당 최대 출전 쿼터 (일반)", min_value=1, value=match_quarters, step=1, help="체력 안배를 위한 인당 최대 출전 쿼터 수")
                min_quarters = st.number_input("인당 최소 출전 보장", min_value=1, value=3, step=1, help="모든 선수가 최소한 뛰어야 하는 쿼터 수")
                no_consecutive_rest = st.checkbox("연속 휴식 금지 (권장)", value=True)

            participants = st.multiselect("참석 인원 선택", options=player_names, default=player_names)
            
            st.write("---")
            st.write("##### 🧤 골키퍼(GK) 설정")
            st.caption("골키퍼를 담당할 선수를 선택하고, 각 선수의 GK 출전 쿼터와 필드 출전 쿼터를 설정하세요.")
            
            gk_players = st.multiselect("골키퍼 선수 선택", options=participants)
            
            gk_settings = {}
            if gk_players:
                cols = st.columns(3)
                for i, gk in enumerate(gk_players):
                    with cols[i % 3]:
                        st.markdown(f"**{gk}**")
                        g_q = st.number_input(f"GK 쿼터", min_value=0, max_value=match_quarters, value=1, key=f"gq_{gk}")
                        f_q = st.number_input(f"필드 쿼터", min_value=0, max_value=match_quarters, value=2, key=f"fq_{gk}")
                        gk_settings[gk] = {'gk': g_q, 'field': f_q}
            
            st.write("---")
            non_gk_participants = [p for p in participants if p not in gk_players]
            low_condition_players = st.multiselect("컨디션 난조/부상 (필드 플레이어 중 최대 2쿼터 제한)", options=non_gk_participants)

        # 2. AI 분석 실행
        if st.button("🚀 AI 라인업 분석 및 생성", type="primary"):
            total_gk_quarters = sum(s['gk'] for s in gk_settings.values()) if gk_settings else 0
            
            if len(participants) < 11:
                st.error("경기를 진행하려면 최소 11명의 선수가 필요합니다.")
            elif not gk_players:
                st.error("최소 1명의 골키퍼를 선택해주세요.")
            elif total_gk_quarters != match_quarters:
                st.error(f"설정된 GK 쿼터의 합({total_gk_quarters})이 전체 경기 쿼터 수({match_quarters})와 일치하지 않습니다. GK 쿼터 수를 조정해주세요.")
            else:
                with st.spinner("전략 파일을 분석하고 라인업을 최적화하는 중..."):
                    # 로직 초기화
                    import random
                    
                    # 쿼터별 GK 배정 (순차 배정)
                    gk_schedule = []
                    for gk in gk_players:
                        gk_schedule.extend([gk] * gk_settings[gk]['gk'])
                    
                    # 쿼터별 할당량 계산
                    field_usage_count = {p: 0 for p in participants} # 필드 출전 수
                    total_usage_count = {p: 0 for p in participants} # 총 출전 수 (GK + 필드)
                    
                    # 최대 출전 제한 설정
                    player_field_limit = {p: max_quarters for p in participants}
                    for p in low_condition_players:
                        player_field_limit[p] = 2
                    for gk, settings in gk_settings.items():
                        player_field_limit[gk] = settings['field']
                    
                    # 결과 저장소
                    quarter_lineups = []
                    last_played_quarter = {p: -1 for p in participants}

                    # 쿼터별 배정 로직 (Greedy)
                    for q in range(1, match_quarters + 1):
                        current_gk = gk_schedule[q-1]
                        
                        # GK 출전 처리
                        total_usage_count[current_gk] += 1
                        last_played_quarter[current_gk] = q
                        
                        # 필드 플레이어 후보군 (GK 제외)
                        field_pool = [p for p in participants if p != current_gk]
                        
                        # 출전 가능 후보군 선정
                        candidates = []
                        for p in field_pool:
                            # 1. 필드 최대 쿼터 제한 체크
                            if field_usage_count[p] >= player_field_limit[p]: continue
                            
                            # 2. 연속 휴식 금지 체크 (직전 쿼터 쉬었으면 우선순위 높임)
                            priority = 0
                            if no_consecutive_rest and (q > 1) and (last_played_quarter[p] != q - 1):
                                priority += 50
                            
                            # 3. 공정성 (출전 수 적은 사람 우선, 최소 쿼터 미달 시 가중치 증가)
                            if total_usage_count[p] < min_quarters:
                                priority += 100
                                
                            priority += (match_quarters - total_usage_count[p]) * 10
                            
                            # 4. 랜덤성 추가 (같은 조건일 때 섞기)
                            priority += random.random()
                            
                            candidates.append((priority, p))
                        
                        # 우선순위 정렬 후 상위 10명 선발
                        candidates.sort(key=lambda x: x[0], reverse=True)
                        selected_field = [x[1] for x in candidates[:10]]
                        
                        # 기록 업데이트
                        for p in selected_field:
                            field_usage_count[p] += 1
                            total_usage_count[p] += 1
                            last_played_quarter[p] = q
                            
                        quarter_lineups.append({
                            "quarter": q,
                            "gk": current_gk,
                            "field": selected_field
                        })

                    # 세션 상태에 잠정 저장 (만약 Gemini 실패 시 기본 할당)
                    st.session_state['quarter_lineups'] = quarter_lineups
                    st.session_state['lineup_summary'] = {
                        'total': total_usage_count,
                        'field': field_usage_count
                    }
                    st.session_state['generated_formation'] = formation
                    st.session_state['tactical_feedbacks'] = {} # 초기화
                    st.session_state['optimized_mappings'] = {} # 초기화
                    
                    # Gemini를 활용하여 각 쿼터별 포지션 최적화 및 전략 피드백 생성
                    try:
                        api_key = st.secrets["GEMINI_API_KEY"]
                    except Exception:
                        api_key = os.getenv("GEMINI_API_KEY")
                    if api_key:
                        try:
                            st.write("### 🧠 AI 감독 포지션 배치 및 전술 분석 중...")
                            progress_bar = st.progress(0)
                            tactical_feedbacks = {}
                            
                            # Gemini 모델 초기화
                            model = genai.GenerativeModel("gemini-2.5-flash")
                            
                            for i, q_lineup in enumerate(quarter_lineups):
                                q_num = q_lineup['quarter']
                                field_players = q_lineup['field']
                                
                                # 선수 스탯 정보 수집
                                player_stats_list = []
                                for p_name in field_players:
                                    match = all_players_df[all_players_df['player_info.name'] == p_name]
                                    if not match.empty:
                                        p_data = match.iloc[0].to_dict()
                                        stat_info = {
                                            "name": p_data.get('player_info.name', p_name),
                                            "main_position": p_data.get('player_info.main_position', 'UNKNOWN'),
                                            "sub_positions": p_data.get('player_info.sub_positions', ''),
                                            "technical": {k: v for k, v in p_data.items() if 'attributes.technical' in k},
                                            "mental": {k: v for k, v in p_data.items() if 'attributes.mental' in k},
                                            "physical": {k: v for k, v in p_data.items() if 'attributes.physical' in k}
                                        }
                                        player_stats_list.append(stat_info)
                                
                                prompt = f"""
                                당신은 안첼로티, 과르디올라 급의 세계적인 명장 축구 감독입니다.
                                이번 쿼터({q_num}쿼터)에 출전이 확정된 10명의 필드 플레이어 명단과 그들의 핵심 능력치 스탯이 제공됩니다.
                                당신이 사용할 전술 포메이션은 {formation} 입니다.
                                
                                <지시사항>
                                1. [포지션 최적화]: 제공된 10명의 선수를 {formation} 포메이션의 10개 위치에 최적화되게 배치하세요. 선수의 체력, 패스, 주력 등을 모두 분석하세요. 선수는 반드시 제공된 10명만 사용해야 하며, 절대 누락이나 외부 인원을 추가해서는 안 됩니다.
                                2. [전술 피드백]: 왜 현재 선발된 10명을 이렇게 배치했는지 강력한 논리로 설명하고, 이번 쿼터 상대방을 공략하기 위한 핵심 전술(빌드업 타겟, 스태미나 안배 등)을 브리핑하세요.
                                
                                출력 형식은 반드시 아래의 JSON 포맷을 그대로 복사하여 사용할 수 있도록 "순수 JSON" 문자열만 출력해 주세요. 마크다운(` ```json ` 등) 블록이나 설명 텍스트를 JSON 텍스트 바깥에 적지 마세요.
                                
                                {{
                                    "optimized_positions": [
                                        {{"name": "선수이름1", "position": "포지션명(예: ST, CM, CB 등)"}},
                                        ...총 10명...
                                    ],
                                    "tactical_feedback": "**[포지션 배치 이유]**\n(설명 내용)\n\n**[이번 쿼터 핵심 전술 가이드]**\n(전술 내용)\n\n**[감독의 종합 의견]**\n(스쿼드 밸런스 총평 등)"
                                }}
                                
                                출전 선수 명단 및 스탯 (JSON):
                                {json.dumps(player_stats_list, ensure_ascii=False)}
                                """
                                
                                response = model.generate_content(prompt)
                                response_text = response.text.strip()
                                
                                # 정규표현식을 사용하여 중괄호 {} 로 둘러싸인 JSON 블록만 추출 (마크다운/채팅 텍스트 무시)
                                json_match = re.search(r'\{[\s\S]*\}', response_text)
                                if json_match:
                                    response_text = json_match.group(0)
                                    
                                try:
                                    ai_result = json.loads(response_text)
                                    # Gemini가 재배치한 순서와 포지션 정보 추합
                                    opt_names = []
                                    opt_positions = {}
                                    for p in ai_result.get('optimized_positions', []):
                                        opt_names.append(p['name'])
                                        opt_positions[p['name']] = p.get('position', 'UNKNOWN')
                                        
                                    if len(opt_names) > 0:
                                        # 최대한 매칭되는 선수만 업데이트
                                        valid_opt_names = [n for n in opt_names if n in field_players]
                                        # 모자란 인원은 기존 명단에서 채움
                                        missing_players = [p for p in field_players if p not in valid_opt_names]
                                        final_field = valid_opt_names + missing_players
                                        quarter_lineups[i]['field'] = final_field[:10]
                                        
                                        # 포지션 매핑 정보를 세션에 저장 (UI 표시용)
                                        if 'optimized_mappings' not in st.session_state:
                                            st.session_state['optimized_mappings'] = {}
                                        st.session_state['optimized_mappings'][q_num] = opt_positions
                                    
                                    # 전략은 이름 검증과 무관하게 항상 표시
                                    tactical_feedbacks[q_num] = ai_result.get('tactical_feedback', "전술 브리핑 정보가 비어있습니다.")
                                except json.JSONDecodeError as e:
                                    print(f"JSON Parsing Error for Q{q_num}: {e}")
                                    print(f"Response Dump: {response_text}")
                                    tactical_feedbacks[q_num] = f"AI 연산 중 포맷 오류 발생.\n\n```json\n{response_text}\n```"
                                except Exception as e:
                                    print(f"Other Error for Q{q_num}: {e}")
                                    tactical_feedbacks[q_num] = f"알 수 없는 오류 발생: {e}"
                                
                                progress_bar.progress(int((i+1) / match_quarters * 100))
                                
                            st.session_state['quarter_lineups'] = quarter_lineups
                            st.session_state['tactical_feedbacks'] = tactical_feedbacks
                            progress_bar.empty()
                        
                        except Exception as e:
                            import traceback
                            error_msg = traceback.format_exc()
                            st.error(f"AI 연동 중 문제가 발생했습니다: {e}")
                            st.session_state['tactical_feedbacks'] = {q['quarter']: f"🚨 **AI 생성 실패**\n오류 내용:\n```python\n{error_msg}\n```" for q in quarter_lineups}
                    else:
                        st.error("GEMINI_API_KEY 환경 변수가 없습니다. `.env` 파일을 확인해주세요.")
                        st.session_state['tactical_feedbacks'] = {q['quarter']: "🚨 **AI 분석 불가**: `.env` 파일에 `GEMINI_API_KEY`가 설정되지 않았습니다." for q in quarter_lineups}

                    st.rerun()

        # 3. 결과 시각화 및 경기 생성 (Session State 기반)
        if 'quarter_lineups' in st.session_state:
            quarter_lineups = st.session_state['quarter_lineups']
            total_usage_count = st.session_state['lineup_summary']['total']
            field_usage_count = st.session_state['lineup_summary']['field']
            
            st.success("✅ 라인업 생성이 완료되었습니다!")
            
            # 요약 대시보드
            st.write("### 📊 배정 결과 요약")
            summary_data = []
            for p in total_usage_count.keys():
                summary_data.append({
                    "선수명": p,
                    "총 출전": total_usage_count[p],
                    "필드": field_usage_count[p],
                    "GK": total_usage_count[p] - field_usage_count[p]
                })
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df.set_index('선수명').T, use_container_width=True)

            # 쿼터별 탭 생성
            tabs = st.tabs([f"{q['quarter']}쿼터" for q in quarter_lineups])
            tactical_feedbacks = st.session_state.get('tactical_feedbacks', {})
            opt_mappings = st.session_state.get('optimized_mappings', {})
            
            for i, tab in enumerate(tabs):
                with tab:
                    lineup = quarter_lineups[i]
                    q_num = lineup['quarter']
                    
                    # 브리핑 출력부분 (전술판보다 먼저 표시되도록 상단에 배치)
                    if tactical_feedbacks and q_num in tactical_feedbacks:
                        st.markdown("### 🎙️ AI 감독의 라커룸 전술 브리핑")
                        st.info(tactical_feedbacks[q_num])
                        st.divider()

                    col_img, col_list = st.columns([2, 1])
                    
                    q_mapping = opt_mappings.get(q_num, {})
                    
                    with col_img:
                        fig = draw_pitch(st.session_state.get('generated_formation', '4-4-2'), lineup['gk'], lineup['field'], all_players_df, q_mapping)
                        st.pyplot(fig, use_container_width=True)
                    
                    with col_list:
                        st.write("#### 📝 출전 명단")
                        st.markdown(f"**🥅 GK (1명)**\n- {lineup['gk']}")
                        
                        # 카테고리별 분류 로직
                        fwd_list = []
                        mid_list = []
                        def_list = []
                        
                        for p in lineup['field']:
                            # AI 할당 포지션이 있으면 그걸 쓰고, 없으면 DB의 main_position을 참조
                            pos = q_mapping.get(p)
                            if not pos or pos == "UNKNOWN":
                                match_db = all_players_df[all_players_df['player_info.name'] == p]
                                if not match_db.empty:
                                    pos = match_db.iloc[0].get('player_info.main_position', 'CM')
                                else:
                                    pos = 'CM'
                                    
                            # 포지션에 따라 3선으로 분류
                            if pos in ['SW', 'CB', 'LB', 'RB', 'LWB', 'RWB']:
                                def_list.append(f"{p} ({pos})")
                            elif pos in ['DM', 'CM', 'LM', 'RM', 'AM']:
                                mid_list.append(f"{p} ({pos})")
                            else: # FWD
                                fwd_list.append(f"{p} ({pos})")
                        
                        st.markdown(f"**⚔️ 공격수 ({len(fwd_list)}명)**")
                        for p in fwd_list: st.markdown(f"- {p}")
                        
                        st.markdown(f"**🛡️ 미드필더 ({len(mid_list)}명)**")
                        for p in mid_list: st.markdown(f"- {p}")
                        
                        st.markdown(f"**🧱 수비수 ({len(def_list)}명)**")
                        for p in def_list: st.markdown(f"- {p}")

            st.divider()
            st.subheader("🗓️ 경기 일정 생성")
            with st.form("create_match_from_lineup"):
                col1, col2 = st.columns(2)
                with col1:
                    match_date = st.date_input("경기 날짜", value=datetime.today())
                with col2:
                    opponent_name = st.text_input("상대 팀 이름")
                
                submitted = st.form_submit_button("✅ 이 라인업으로 경기 생성")
                
                if submitted:
                    if not opponent_name:
                        st.error("상대 팀 이름을 입력해주세요.")
                    else:
                        matches = load_matches_data()
                        
                        # 이름 -> ID 매핑
                        name_to_id = dict(zip(all_players_df['player_info.name'], all_players_df['id']))
                        
                        # 라인업에 포함된 모든 선수 ID 추출
                        lineup_ids = set()
                        for q in quarter_lineups:
                            if q['gk'] in name_to_id: lineup_ids.add(name_to_id[q['gk']])
                            for p in q['field']:
                                if p in name_to_id: lineup_ids.add(name_to_id[p])
                        
                        new_match = {
                            "id": str(uuid.uuid4()),
                            "date": match_date.strftime("%Y-%m-%d"),
                            "opponent": opponent_name,
                            "status": "scheduled",
                            "lineup": list(lineup_ids),
                            "quarter_lineups": quarter_lineups,
                            "result": {}
                        }
                        
                        matches.append(new_match)
                        save_matches_data(matches)
                        
                        # 세션 초기화
                        del st.session_state['quarter_lineups']
                        st.success(f"{match_date} vs {opponent_name} 경기가 생성되었습니다!")
                        st.rerun()

elif selected_menu == '경기 목록':
    st.write("생성된 경기 목록을 확인합니다. 경기 결과 기록은 '경기 결과 기록' 탭에서 할 수 있습니다.")
    
    matches = load_matches_data()
    
    if not matches:
        st.info("아직 생성된 경기가 없습니다. 'AI 라인업 생성' 탭에서 경기를 생성해주세요.")
    else:
        # 결과를 보기 쉽게 DataFrame으로 변환
        display_data = []
        for m in matches:
            res = m.get('result', {})
            score = f"{res.get('home_score', '-')} : {res.get('away_score', '-')}" if m.get('status') == 'completed' else "경기 전"
            display_data.append({
                "날짜": m.get('date'),
                "상대": m.get('opponent'),
                "상태": {"scheduled": "예정", "completed": "종료"}.get(m.get('status'), m.get('status')),
                "결과": score
            })
        
        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)

    if st.button("🔄 경기 목록 새로고침"):
        st.rerun()

elif selected_menu == '경기 결과 기록':
    st.write("예정된 경기의 결과를 기록하고 선수 스탯을 업데이트합니다.")

    matches = load_matches_data()
    players_df = load_players_data()
    
    # id를 이름으로 매핑하는 딕셔너리 생성
    player_id_to_name = pd.Series(players_df['player_info.name'].values, index=players_df['id']).to_dict() if not players_df.empty else {}
    name_to_player_id = {v: k for k, v in player_id_to_name.items()}

    scheduled_matches = [m for m in matches if m.get('status') == 'scheduled']

    if not scheduled_matches:
        st.info("결과를 기록할 예정된 경기가 없습니다.")
    else:
        match_options = {f"{m['date']} vs {m['opponent']}": m['id'] for m in scheduled_matches}
        selected_match_display = st.selectbox("결과를 기록할 경기를 선택하세요", options=list(match_options.keys()))
        
        selected_match_id = match_options.get(selected_match_display)
        if selected_match_id:
            selected_match = next((m for m in scheduled_matches if m['id'] == selected_match_id), None)
            
            if selected_match:
                st.write("---")
                st.subheader(f"'{selected_match_display}' 결과 입력")
                
                lineup_ids = selected_match.get('lineup', [])
                lineup_names = [player_id_to_name.get(pid, "알 수 없는 선수") for pid in lineup_ids]

                with st.form("match_result_form"):
                    st.write("##### 경기 결과")
                    col1, col2 = st.columns(2)
                    with col1:
                        home_score = st.number_input("홈 팀 점수", min_value=0, step=1, key="home_score")
                    with col2:
                        away_score = st.number_input("원정 팀 점수", min_value=0, step=1, key="away_score")

                    scorers_names = st.multiselect("득점 선수", options=lineup_names)
                    assists_names = st.multiselect("도움 선수", options=lineup_names)

                    st.write("##### 선수 평점 (1.0-10.0)")
                    player_ratings = {}
                    # 2열로 선수 평점 슬라이더 표시
                    player_cols = st.columns(2)
                    for i, (player_name, player_id) in enumerate(zip(lineup_names, lineup_ids)):
                        with player_cols[i % 2]:
                            player_ratings[player_id] = st.slider(player_name, min_value=1.0, max_value=10.0, value=6.0, step=0.1)

                    submitted = st.form_submit_button("경기 종료")

                    if submitted:
                        with st.spinner("경기 결과를 저장하고 선수 스탯을 업데이트하는 중..."):
                            # 1. 선택된 경기 정보 업데이트
                            scorers_ids = [name_to_player_id[name] for name in scorers_names]
                            assists_ids = [name_to_player_id[name] for name in assists_names]

                            selected_match['status'] = 'completed'
                            selected_match['result'] = {
                                'home_score': home_score,
                                'away_score': away_score,
                                'scorers': scorers_ids,
                                'assists': assists_ids,
                                'ratings': player_ratings
                            }
                            
                            # 전체 경기 목록에서 현재 경기 업데이트
                            matches = [selected_match if m['id'] == selected_match_id else m for m in matches]

                            # 2. 선수 스탯 업데이트
                            for player_id in lineup_ids:
                                # players_df에서 해당 선수 찾기
                                player_row = players_df[players_df['id'] == player_id]
                                if not player_row.empty:
                                    player_idx = player_row.index[0]
                                    
                                    # 평균 평점 계산
                                    current_apps = players_df.loc[player_idx, 'player_info.total_apps']
                                    current_avg_rating = players_df.loc[player_idx, 'player_info.average_rating']
                                    new_rating = player_ratings[player_id]

                                    # 이전 기록이 없는 경우 처리 (NaN)
                                    if pd.isna(current_apps) or current_apps == 0 or pd.isna(current_avg_rating):
                                        new_avg = new_rating
                                        new_apps = 1
                                    else:
                                        # 정수형 변환 추가
                                        current_apps = int(current_apps)
                                        new_apps = current_apps + 1
                                        new_avg = ((current_avg_rating * current_apps) + new_rating) / new_apps

                                    players_df.loc[player_idx, 'player_info.total_apps'] = new_apps
                                    players_df.loc[player_idx, 'player_info.average_rating'] = new_avg
                            
                            # 3. 데이터 저장
                            save_matches_data(matches)
                            save_players_data(players_df)

                        st.success(f"'{selected_match_display}' 경기가 종료되고 결과가 저장되었습니다!")
                        st.rerun()

if not firebase_initialized:
    st.toast("Firebase에 연결되지 않아 일부 기능이 제한될 수 있습니다.")
