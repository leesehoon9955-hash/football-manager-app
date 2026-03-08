
import random
import uuid

def generate_dummy_players(num_players=15):
    """지정된 수만큼의 테스트 선수 데이터를 생성합니다."""
    names = ["김민재", "손흥민", "이강인", "황희찬", "조규성", "박지성", "이영표", "차범근", "홍명보", "황선홍", "유상철", "안정환", "김남일", "이운재", "박주영"]
    positions = ["ST", "LW", "RW", "CM", "CDM", "CB", "LB", "RB"]
    feet = ["오른발", "왼발"]
    players = []

    # 기술, 정신, 신체 능력치 목록
    tech_attrs = ["dribbling", "man_marking", "passing", "shooting", "tackling", "first_touch", "crossing", "heading"]
    mental_attrs = ["aggression", "anticipation", "composure", "concentration", "decisions", "teamwork", "vision", "positioning"]
    physical_attrs = ["acceleration", "pace", "stamina", "strength", "agility", "jumping_reach", "natural_fitness"]

    for i in range(num_players):
        player = {
            "player_info": {
                "name": names[i] if i < len(names) else f"선수 {i+1}",
                "age": random.randint(18, 38),
                "preferred_foot": random.choice(feet),
                "main_position": random.choice(positions),
                "sub_positions": random.sample(positions, 2),
                "total_apps": random.randint(0, 100),
                "average_rating": round(random.uniform(6.5, 8.5), 2)
            },
            "status": {
                "condition": random.randint(1, 5),
                "injury_risk": random.choice(["없음", "하", "중"])
            },
            "attributes": {
                "technical": {attr: random.randint(5, 20) for attr in tech_attrs},
                "mental": {attr: random.randint(5, 20) for attr in mental_attrs},
                "physical": {attr: random.randint(5, 20) for attr in physical_attrs}
            },
            "match_history": [],
            "id": str(uuid.uuid4())
        }
        players.append(player)
    return players

def unflatten_dict(d):
    """dot-notation의 딕셔너리를 nested 딕셔너리로 변환합니다."""
    result = {}
    for key, value in d.items():
        parts = key.split('.')
        d_temp = result
        for part in parts[:-1]:
            if part not in d_temp:
                d_temp[part] = {}
            d_temp = d_temp[part]
        d_temp[parts[-1]] = value
    return result


# ────────────────────────────────────────────────
# 🔬 [테스트 전용] 데이터 일관성 검증 유틸리티
# ENABLE_VERIFICATION = False 로 설정하면 기능이 완전히 비활성화됩니다.
# ────────────────────────────────────────────────
ENABLE_VERIFICATION = True

# 포메이션별 필드 슬롯 수 (GK 제외)
_FORMATION_SLOTS = {
    "4-4-2": 10,
    "4-3-3": 10,
    "3-5-2": 10,
}
_FIELD_PLAYER_COUNT = 10


def verify_lineup_consistency(data: dict) -> dict:
    """
    라인업 데이터의 내부 일관성을 5가지 항목으로 검사합니다.

    Parameters
    ----------
    data : dict
        {
          "quarter_lineups":   list[{'quarter':int, 'gk':str, 'field':list[str]}],
          "tactical_feedbacks": dict[int, str],
          "optimized_mappings": dict[int, dict[str, str]],
          "formation": str  (e.g. "4-4-2")
        }

    Returns
    -------
    dict
        {
          "summary": "PASS" | "FAIL",
          "checks": [{"name":str, "status":"PASS"|"FAIL"|"WARN",
                      "quarter": int|None, "detail": str}]
        }
    """
    quarter_lineups   = data.get("quarter_lineups", [])
    tactical_feedbacks = data.get("tactical_feedbacks", {})
    optimized_mappings = data.get("optimized_mappings", {})
    formation         = data.get("formation", "4-4-2")
    expected_field    = _FORMATION_SLOTS.get(formation, _FIELD_PLAYER_COUNT)

    checks = []

    # ── 검사 1: 쿼터별 선수 수 ──────────────────────────────
    for q in quarter_lineups:
        q_num      = q.get("quarter")
        gk         = q.get("gk", "")
        field      = q.get("field", [])
        field_ok   = len(field) == expected_field
        gk_ok      = bool(gk)

        if field_ok and gk_ok:
            status = "PASS"
            detail = f"GK 1명, 필드 {len(field)}명 — 정상"
        else:
            status = "FAIL"
            parts = []
            if not gk_ok:
                parts.append("GK 미배정")
            if not field_ok:
                parts.append(f"필드 선수 {len(field)}명 (기대값: {expected_field}명)")
            detail = " / ".join(parts)

        checks.append({
            "name": "쿼터별 선수 수",
            "status": status,
            "quarter": q_num,
            "detail": detail,
        })

    # ── 검사 2: 동일 쿼터 내 선수 중복 ──────────────────────
    for q in quarter_lineups:
        q_num   = q.get("quarter")
        gk      = q.get("gk", "")
        field   = q.get("field", [])
        all_p   = [gk] + field if gk else field
        seen    = set()
        dups    = []
        for p in all_p:
            if p in seen:
                dups.append(p)
            seen.add(p)

        if not dups:
            checks.append({"name": "선수 중복", "status": "PASS",
                            "quarter": q_num, "detail": "중복 없음"})
        else:
            checks.append({"name": "선수 중복", "status": "FAIL",
                            "quarter": q_num,
                            "detail": f"중복 선수: {', '.join(dups)}"})

    # ── 검사 3: AI 포지션 매핑 선수 수 ──────────────────────
    for q in quarter_lineups:
        q_num  = q.get("quarter")
        field  = q.get("field", [])
        mapping = optimized_mappings.get(q_num, {})

        if not mapping:
            checks.append({"name": "AI 포지션 매핑 수", "status": "WARN",
                            "quarter": q_num,
                            "detail": "AI 매핑 없음 (AI 미실행 또는 파싱 실패)"})
            continue

        mapped_names = set(mapping.keys())
        field_names  = set(field)
        extra   = mapped_names - field_names   # 매핑에는 있지만 명단에 없는 이름
        missing = field_names  - mapped_names  # 명단에는 있지만 매핑에 없는 이름

        if not extra and not missing:
            checks.append({"name": "AI 포지션 매핑 수", "status": "PASS",
                            "quarter": q_num,
                            "detail": f"매핑 {len(mapping)}명 — 명단과 일치"})
        else:
            parts = []
            if extra:
                parts.append(f"명단 외 선수: {', '.join(extra)}")
            if missing:
                parts.append(f"매핑 누락: {', '.join(missing)}")
            checks.append({"name": "AI 포지션 매핑 수", "status": "FAIL",
                            "quarter": q_num, "detail": " / ".join(parts)})

    # ── 검사 4: 전술 분석 텍스트 선수명 Hallucination ────────
    # 명단에 없는 이름이 전술 분석에 등장하면 WARN
    for q in quarter_lineups:
        q_num   = q.get("quarter")
        gk      = q.get("gk", "")
        field   = q.get("field", [])
        all_names = set([gk] + field) if gk else set(field)
        feedback  = tactical_feedbacks.get(q_num, "")

        if not feedback:
            checks.append({"name": "전술분석 선수명 검증", "status": "WARN",
                            "quarter": q_num, "detail": "전술 분석 텍스트 없음"})
            continue

        # 명단에 없는 이름이 텍스트에 등장하는지 검사
        # (2자 이상 한글 토큰 중 all_names 에 없는 것)
        import re as _re
        text_tokens = set(_re.findall(r'[가-힣A-Za-z]{2,}', feedback))
        # 전술 용어 제외 (포지션, 전술 관련 단어)
        tactic_words = {
            "포지션", "포메이션", "전술", "쿼터", "수비", "공격", "미드필더",
            "빌드업", "스태미나", "패스", "압박", "역습", "체력", "골키퍼",
            "라인업", "선발", "교체", "슈팅", "드리블", "태클", "크로스",
            "헤딩", "스위퍼", "윙백", "스트라이커", "포워드", "디펜더",
            "감독", "브리핑", "배치", "이유", "전략", "가이드", "의견",
            "핵심", "종합", "안배", "타겟", "우선", "활용", "강점", "약점",
            "LB", "RB", "CB", "CM", "LM", "RM", "ST", "CF", "LW", "RW",
            "DM", "AM", "GK", "SW", "SS", "WB", "LWB", "RWB",
        }
        # 실제 출전 선수 이름이 아닌 한글 이름 토큰 중 tactic_words 에도 없는 것
        hallucinated = []
        for tok in text_tokens:
            # 한글 2자 이상이면서 명단에 없고 전술 단어도 아닌 것 — 잠재적 Hallucination
            if _re.fullmatch(r'[가-힣]{2,}', tok) and tok not in all_names and tok not in tactic_words:
                hallucinated.append(tok)

        if not hallucinated:
            checks.append({"name": "전술분석 선수명 검증", "status": "PASS",
                            "quarter": q_num,
                            "detail": "명단 외 선수명 미감지"})
        else:
            checks.append({"name": "전술분석 선수명 검증", "status": "WARN",
                            "quarter": q_num,
                            "detail": f"명단 외 토큰(잠재적 Hallucination): {', '.join(hallucinated[:10])}"})

    # ── 검사 5: 이미지 렌더링 입력 데이터 일치 ───────────────
    # draw_pitch()에는 (formation, gk, field, ..., opt_mapping) 이 전달됨
    # → session_state의 quarter_lineups / optimized_mappings 와 동일 출처이므로
    #   데이터 레벨에서 필드 리스트와 매핑 키가 일치하는지 검사
    for q in quarter_lineups:
        q_num   = q.get("quarter")
        field   = q.get("field", [])
        mapping = optimized_mappings.get(q_num, {})

        # 매핑이 있을 때만 검사 (없으면 검사 3에서 이미 WARN 처리)
        if not mapping:
            continue

        mapped_keys = set(mapping.keys())
        field_set   = set(field)

        if mapped_keys <= field_set:   # 매핑 키가 field 의 부분집합이면 OK
            checks.append({"name": "이미지 렌더링 입력 일치", "status": "PASS",
                            "quarter": q_num,
                            "detail": "렌더링 입력(field, opt_mapping) 일치"})
        else:
            ghost = mapped_keys - field_set
            checks.append({"name": "이미지 렌더링 입력 일치", "status": "FAIL",
                            "quarter": q_num,
                            "detail": f"opt_mapping에만 존재하는 선수: {', '.join(ghost)}"})

    # ── 최종 판정 ─────────────────────────────────────────
    has_fail = any(c["status"] == "FAIL" for c in checks)
    summary  = "FAIL" if has_fail else "PASS"

    return {"summary": summary, "checks": checks}


def run_verification_report(data: dict) -> dict | None:
    """
    verify_lineup_consistency() 를 실행하고 결과를 stdout 에 출력합니다.
    ENABLE_VERIFICATION = False 이면 즉시 None 을 반환합니다.

    Parameters
    ----------
    data : dict  (verify_lineup_consistency() 와 동일)

    Returns
    -------
    dict | None  — 검증 결과 dict 또는 None (비활성화 시)
    """
    if not ENABLE_VERIFICATION:
        print("[Verification] ENABLE_VERIFICATION = False — 검증 기능 비활성화됨")
        return None

    result = verify_lineup_consistency(data)
    summary = result["summary"]

    print("=" * 60)
    print(f"[Verification Report]  종합 결과: {summary}")
    print("=" * 60)

    status_icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
    for c in result["checks"]:
        icon = status_icon.get(c["status"], "?")
        q_label = f" Q{c['quarter']}" if c["quarter"] is not None else ""
        print(f"  {icon} [{c['status']}]{q_label}  {c['name']} — {c['detail']}")

    print("=" * 60)
    return result
