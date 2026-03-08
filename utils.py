
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
