import streamlit as st
from google import genai
import json
import re
import folium
from streamlit_folium import st_folium
import datetime
import random
import urllib.parse
import pandas as pd

# ==========================================
# 🚨 API 키 (테스트 시에만 입력하세요!)
# ==========================================
API_KEY = ""

st.set_page_config(page_title="제로 플랜: 알아서 갈게", layout="wide")

# 💡 피드백 반영: 왼쪽 사이드바에 비상 초기화 버튼 탑재
with st.sidebar:
    st.markdown("### 🔄 새로운 여행 준비")
    st.caption("여행지가 바뀌었거나, 장바구니가 꼬였을 때 눌러주세요.")
    if st.button("🚨 처음부터 다시 짜기", type="primary", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.markdown("---")
    st.markdown("💡 **제로 플랜 이용 가이드**")
    st.markdown("1. 출발지와 목적지를 입력하세요.\n2. AI가 찾아준 명소를 바구니에 담으세요.\n3. 동선과 맛집을 자동으로 연결해 줍니다.")

st.title("✈️ 제로 플랜 (Zero Plan) : 알아서 갈게")
st.markdown("**10초 만에 끝나는 AI 여행 설계 및 실시간 트러블 슈팅 시스템**")

THEME_CATEGORIES = ["랜드마크", "역사/전통", "자연/풍경", "쇼핑", "테마파크/액티비티", "야경", "문화/예술", "📸 인스타 핫플", "기타"]

def toggle_place(place_name):
    if place_name in st.session_state.selected_places: st.session_state.selected_places.remove(place_name)
    else: st.session_state.selected_places.append(place_name)

def toggle_food(day_label, food_name):
    if day_label not in st.session_state.selected_food: st.session_state.selected_food[day_label] = []
    if food_name in st.session_state.selected_food[day_label]: st.session_state.selected_food[day_label].remove(food_name)
    else: st.session_state.selected_food[day_label].append(food_name)

# --- 세션 초기화 ---
if 'travel_data' not in st.session_state: st.session_state.travel_data = None
if 'selected_places' not in st.session_state: st.session_state.selected_places = []
if 'optimized_itinerary' not in st.session_state: st.session_state.optimized_itinerary = None
if 'all_places_dict' not in st.session_state: st.session_state.all_places_dict = {}

if 'food_recommendations' not in st.session_state: st.session_state.food_recommendations = None
if 'selected_food' not in st.session_state: st.session_state.selected_food = {}
if 'all_food_dict' not in st.session_state: st.session_state.all_food_dict = {}

if 'pill_key_counter' not in st.session_state: st.session_state.pill_key_counter = 0
if 'step' not in st.session_state: st.session_state.step = 1

if 'last_searched_city' not in st.session_state: st.session_state.last_searched_city = ""

if 'url_loaded' not in st.session_state:
    st.session_state.url_loaded = True
    if "p" in st.query_params:
        shared_places_str = st.query_params["p"]
        if shared_places_str:
            st.session_state.selected_places = shared_places_str.split("|")
            st.session_state.step = 2
            st.toast("🔗 공유받은 여행 일정을 성공적으로 불러왔습니다!", icon="🎉")

# ==========================================
# 💡 4단계 내비게이션 바
# ==========================================
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)
with nav_col1:
    if st.button("📍 1. 명소 담기", use_container_width=True, type="primary" if st.session_state.step == 1 else "secondary"): st.session_state.step = 1; st.rerun()
with nav_col2:
    if st.button("🗓️ 2. 동선 짜기", use_container_width=True, type="primary" if st.session_state.step == 2 else "secondary"): st.session_state.step = 2; st.rerun()
with nav_col3:
    if st.button("🍔 3. 맛집/카페", use_container_width=True, type="primary" if st.session_state.step == 3 else "secondary"): st.session_state.step = 3; st.rerun()
with nav_col4:
    if st.button("✨ 4. 최종 완성", use_container_width=True, type="primary" if st.session_state.step == 4 else "secondary"): st.session_state.step = 4; st.rerun()

st.markdown("---")

# ==========================================
# [1단계 화면]
# ==========================================
if st.session_state.step == 1:
    st.subheader("📅 여행 기본 정보")
    
    col0, col1, col2, col3 = st.columns([1, 1, 1.5, 1])
    with col0:
        departure = st.text_input("출발지", value="서울")
        st.session_state.departure = departure
    with col1: 
        city = st.text_input("목적지 (베이스캠프)", value="오사카")
        st.session_state.city = city
    with col2:
        default_start = datetime.date(2026, 4, 1)
        default_end = datetime.date(2026, 4, 5)
        travel_dates = st.date_input("여행 일자", value=[default_start, default_end], min_value=datetime.date.today())
        st.session_state.travel_dates = travel_dates
    with col3:
        num_people = st.number_input("여행 인원 (명)", min_value=1, max_value=20, value=2)
        st.session_state.num_people = num_people

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### 🚆 이동 스케줄 & 🏨 숙소 정보")
    opt_col1, opt_col2, opt_col3 = st.columns(3)
    with opt_col1:
        flight_arr = st.selectbox("첫날 목적지 도착 시간", ["미정 (종일 일정)", "오전 (9시~12시)", "오후 (12시~17시)", "저녁 (17시 이후)"])
        st.session_state.flight_arr = flight_arr
    with opt_col2:
        flight_dep = st.selectbox("마지막 날 출발 시간", ["미정 (종일 일정)", "오전 (9시~12시)", "오후 (12시~17시)", "저녁 (17시 이후)"])
        st.session_state.flight_dep = flight_dep
    with opt_col3:
        basecamp_hotel = st.text_input("나의 베이스캠프 (숙소명)", placeholder="예: 난바 오리엔탈 호텔", help="일정 내내 머물 단일 숙소를 적어주세요.")
        st.session_state.basecamp_hotel = basecamp_hotel if basecamp_hotel else "숙소 (미정)"

    if st.button("🔍 순수 관광지 데이터 수집", type="primary"):
        if not city or len(travel_dates) != 2:
            st.warning("목적지와 일자를 확인해주세요.")
        else:
            # 💡 피드백 완벽 반영: 목적지가 바뀌면 2,3,4단계 결과물까지 싸그리 파기!
            if st.session_state.last_searched_city != "" and st.session_state.last_searched_city != city:
                st.session_state.selected_places = []
                st.session_state.optimized_itinerary = None
                st.session_state.food_recommendations = None
                st.session_state.selected_food = {}
                st.session_state.all_food_dict = {}
                st.toast("목적지가 변경되어 과거 일정을 모두 초기화했습니다!", icon="🧹")
            
            st.session_state.last_searched_city = city

            with st.spinner(f"AI가 {city}의 순수 관광 핫플만 엄선 중입니다... (약 30초 소요)"):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt = f"""
                    여행지 '{city}'의 관광 장소 데이터를 수집. 카테고리: {THEME_CATEGORIES}
                    1. 쇼핑, 핫플, 랜드마크 위주로 가장 유명한 곳 30~40개만 빠르고 정확하게 생성.
                    2. 숙소, 식당, 카페 절대 제외. (중복 불가)
                    {{ "regions": [ {{ "city_name": "도시명", "places": [ {{"name": "이름", "description": "1줄 요약", "theme": "테마", "lat": 위도, "lng": 경도}} ] }} ] }}
                    """
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    match = re.search(r'\{.*\}', response.text, re.DOTALL)
                    if match:
                        st.session_state.travel_data = json.loads(match.group(0))
                        st.session_state.all_places_dict = {}
                        for r in st.session_state.travel_data['regions']:
                            for p in r['places']: st.session_state.all_places_dict[p['name']] = p
                except Exception as e: st.error(f"오류: {e}")

    if st.session_state.travel_data:
        data = st.session_state.travel_data
        st.divider()
        
        if st.button("✨ AI 추천 명소 알아서 꽉꽉 담아주기"):
            dates = st.session_state.get('travel_dates', [datetime.date.today(), datetime.date.today()])
            days = max(1, (dates[1] - dates[0]).days + 1) 
            target_picks = days * 4 
            
            all_places_available = []
            for region in data['regions']: all_places_available.extend(region['places'])
            target_picks = min(target_picks, len(all_places_available))
            
            picks = random.sample(all_places_available, target_picks)
            auto_picks = [p['name'] for p in picks]
            st.session_state.selected_places = list(set(st.session_state.selected_places + auto_picks))

        list_col, map_col = st.columns([1.5, 1])
        with list_col:
            filter_col1, filter_col2 = st.columns([4, 1])
            with filter_col1: selected_themes = st.pills("테마 필터링", THEME_CATEGORIES, selection_mode="multi", key=f"theme_pills_{st.session_state.pill_key_counter}")
            with filter_col2: 
                if st.button("🔄 필터 초기화", use_container_width=True): st.session_state.pill_key_counter += 1; st.rerun()

            with st.container(height=400):
                tabs = st.tabs([r['city_name'] for r in data['regions']])
                for i, tab in enumerate(tabs):
                    with tab:
                        places_in_city = data['regions'][i]['places']
                        if selected_themes: places_in_city = [p for p in places_in_city if p['theme'] in selected_themes]
                        grid_cols = st.columns(2)
                        for idx, place in enumerate(places_in_city):
                            with grid_cols[idx % 2]:
                                with st.container(border=True):
                                    st.markdown(f"**{place['name']}**")
                                    st.caption(f"[{place['theme']}]")
                                    is_selected = place['name'] in st.session_state.selected_places
                                    st.checkbox("일정에 담기", value=is_selected, key=f"chk_{i}_{idx}_{place['name']}", on_change=toggle_place, args=(place['name'],))
            
            st.markdown("---")
            custom_col1, custom_col2 = st.columns([3, 1])
            with custom_col1: custom_place = st.text_input("수동 장소 추가", placeholder="예: 덴덴타운", label_visibility="collapsed")
            with custom_col2:
                if st.button("➕ 직접 추가", use_container_width=True) and custom_place:
                    with st.spinner("검색 중..."):
                        try:
                            client = genai.Client(api_key=API_KEY)
                            resp_custom = client.models.generate_content(model="gemini-2.5-flash", contents=f"'{city}'의 '{custom_place}' JSON 출력: {{\"name\": \"{custom_place}\", \"description\": \"요약\", \"theme\": \"기타\", \"lat\": 위도, \"lng\": 경도}}")
                            match_custom = re.search(r'\{.*\}', resp_custom.text, re.DOTALL)
                            if match_custom:
                                new_place = json.loads(match_custom.group(0))
                                st.session_state.travel_data['regions'][0]['places'].append(new_place)
                                st.session_state.all_places_dict[new_place['name']] = new_place
                                if new_place['name'] not in st.session_state.selected_places: st.session_state.selected_places.append(new_place['name'])
                                st.rerun()
                        except Exception: st.error("장소를 찾지 못했습니다.")

            if st.session_state.selected_places:
                with st.container(border=True):
                    cart_header_col1, cart_header_col2 = st.columns([3, 1])
                    with cart_header_col1: st.markdown(f"**🛒 현재 바구니 ({len(st.session_state.selected_places)}곳)**")
                    with cart_header_col2:
                        if st.button("🗑️ 전체 비우기", use_container_width=True):
                            st.session_state.selected_places = []
                            st.rerun()

                    btn_cols = st.columns(4)
                    for idx, p_name in enumerate(list(st.session_state.selected_places)):
                        with btn_cols[idx % 4]:
                            if st.button(f"❌ {p_name}", key=f"del_{p_name}"): st.session_state.selected_places.remove(p_name); st.rerun()

        with map_col:
            st.subheader(f"🎒 바구니 현황")
            m = folium.Map()
            selected_data = [st.session_state.all_places_dict[name] for name in st.session_state.selected_places if name in st.session_state.all_places_dict]
            valid_map_data = [p for p in selected_data if p.get('lat') and p.get('lng')]
            if valid_map_data:
                lats = [p['lat'] for p in valid_map_data]; lngs = [p['lng'] for p in valid_map_data]
                for p in valid_map_data: folium.Marker([p['lat'], p['lng']], popup=p['name'], icon=folium.Icon(color='red')).add_to(m)
                m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]])
            st_folium(m, width="stretch", height=500)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 선택 완료! 2단계로 넘어가서 뼈대 동선 짜기 ➔", type="primary", use_container_width=True):
            if len(st.session_state.selected_places) < 3: st.warning("⚠️ 최소 3개 이상의 장소를 담아주세요!")
            else: st.session_state.step = 2; st.rerun()

# ==========================================
# [2단계 화면] 동선 뼈대 잡기
# ==========================================
elif st.session_state.step == 2:
    if len(st.session_state.selected_places) < 3:
        st.info("최소 3개 이상의 장소를 바구니에 담아주세요.")
    else:
        if st.button("🚀 AI 마스터 동선 생성", type="primary"):
            loading_ui = st.empty()
            with loading_ui.container(): st.write("#### ✈️ 숙소 위치와 도착/출발 시간을 분석하여 최적의 뼈대를 계산 중입니다... (약 30초 소요)")
            try:
                client = genai.Client(api_key=API_KEY)
                selected_details = [st.session_state.all_places_dict[name] for name in st.session_state.selected_places if name in st.session_state.all_places_dict]
                dates = st.session_state.get('travel_dates')
                hotel = st.session_state.get('basecamp_hotel')
                
                prompt_itinerary = f"""
                여행 기간: {dates[0]} 부터 {dates[1]} 까지. 숙소: {hotel}. 
                이동 스케줄: 도착({st.session_state.get('flight_arr')}), 출발({st.session_state.get('flight_dep')})
                방문 장소: {json.dumps(selected_details, ensure_ascii=False)}
                
                [조건]
                1. 모든 일자의 첫 장소와 마지막 장소는 무조건 '{hotel}'로 설정하세요.
                2. 도착 시간이 '오전/오후'라면 첫날 일정을 충분히 알차게 채우고, '저녁'일 경우에만 가볍게 1곳만 넣으세요.
                3. 마지막 날 출발 시간이 '오후/저녁'이면 마지막 날 오전 일정을 알차게 넣으세요.
                4. 장소와 장소 사이의 이동 수단과 예상 시간을 'transit_info'에 반드시 적으세요 (예: 🚇 지하철 15분).
                
                순수 JSON 형식:
                {{ "itinerary": [ {{ "day": 1, "date": "YYYY-MM-DD", "theme_of_day": "컨셉", "route": [ {{ "name": "장소명", "lat": 위도, "lng": 경도, "reason": "이유", "transit_info": "이동 정보" }} ] }} ] }}
                """
                resp_itinerary = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_itinerary)
                match_iti = re.search(r'\{.*\}', resp_itinerary.text, re.DOTALL)
                if match_iti: st.session_state.optimized_itinerary = json.loads(match_iti.group(0))
            except Exception as e: st.error(f"오류: {e}")
            finally: loading_ui.empty()

        if st.session_state.optimized_itinerary:
            iti_data = st.session_state.optimized_itinerary['itinerary']
            
            day_options = [f"Day {d['day']} ({d['date']})" for d in iti_data]
            selected_day_label = st.selectbox("🗺️ 확인하고 싶은 일자를 선택하세요:", day_options)
            selected_idx = day_options.index(selected_day_label)
            day_info = iti_data[selected_idx]
            
            st.markdown(f"### ✨ {day_info['theme_of_day']}")
            col_timeline, col_daymap = st.columns([1, 1])
            day_places = day_info['route']
            
            with col_timeline:
                for idx, step in enumerate(day_places):
                    with st.container(border=True):
                        is_hotel = st.session_state.get('basecamp_hotel') in step['name']
                        icon = "🏨" if is_hotel else f"{idx+1}."
                        st.markdown(f"**{icon} {step['name']}**")
                        st.caption(f"💡 {step['reason']}")
                        
                        transit_str = step.get('transit_info', '일정 종료')
                        if idx < len(day_places) - 1:
                            next_step = day_places[idx + 1]
                            if step.get('lat') and step.get('lng') and next_step.get('lat') and next_step.get('lng'):
                                google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={step['lat']},{step['lng']}&destination={next_step['lat']},{next_step['lng']}&travelmode=transit"
                                st.info(f"➔ {transit_str}  |  [🗺️ 구글 지도로 실제 길찾기]({google_maps_url})")
                            else:
                                st.info(f"➔ {transit_str}")
                        else:
                            st.info("🌙 오늘의 일정 종료 및 숙소 휴식")
            
            with col_daymap:
                m_day = folium.Map()
                valid_places = [p for p in day_places if p.get('lat') and p.get('lng')]
                if valid_places:
                    lats = [p['lat'] for p in valid_places]; lngs = [p['lng'] for p in valid_places]
                    for idx, p in enumerate(valid_places):
                        color = 'green' if st.session_state.get('basecamp_hotel') in p['name'] else 'red'
                        folium.Marker([p['lat'], p['lng']], popup=p['name'], icon=folium.Icon(color=color)).add_to(m_day)
                    folium.PolyLine([[p['lat'], p['lng']] for p in valid_places], color="#FF4B4B", weight=3).add_to(m_day)
                    m_day.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]])
                st_folium(m_day, width="stretch", height=400, key=f"map_day_{selected_idx}")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🍔 동선이 완성되었습니다! 3단계로 넘어가서 식당 채우기 ➔", type="primary", use_container_width=True):
            if not st.session_state.optimized_itinerary: st.warning("⚠️ 동선을 먼저 생성해주세요!")
            else: st.session_state.step = 3; st.rerun()

# ==========================================
# [3단계 화면] 맛집 한 번에 찾기 & 수동 추가
# ==========================================
elif st.session_state.step == 3:
    if not st.session_state.optimized_itinerary:
        st.info("2단계에서 동선을 먼저 만들어주세요.")
    else:
        st.markdown("### 🍔 전체 일정 맞춤형 맛집/카페 찾기")
        st.caption("AI가 1~5일 차의 동선을 한 번에 분석하여, 동선에 딱 맞는 쾌적한 맛집과 인스타/블로그 핫플 카페를 찾아옵니다.")
        
        iti_data = st.session_state.optimized_itinerary['itinerary']

        if st.button("✨ 1~5일 차 맛집/카페 한 번에 싹 다 찾기!", type="primary"):
            with st.spinner("전체 일정에 맞는 맛집과 감성 카페를 탐색 중입니다... (약 30초 ~ 1분 소요)"):
                try:
                    client = genai.Client(api_key=API_KEY)
                    prompt_food = f"""
                    다음은 사용자의 전체 여행 일정입니다: {json.dumps(iti_data, ensure_ascii=False)}
                    각 Day별 방문 장소들을 파악하고, 그 근처에서 방문하기 좋은 곳을 추천해주세요.
                    
                    [절대 조건]
                    1. 각 Day별로 위생적인 '로컬 맛집' 2곳, 인스타/블로그에서 평이 좋은 '트렌디한 카페' 1곳을 추천.
                    2. 모든 Day(1일 차~마지막 날)에 대해 빠짐없이 데이터를 생성.
                    
                    순수 JSON 형식으로만 응답:
                    {{
                        "Day 1": [ {{"name": "식당명", "type": "맛집 또는 카페", "description": "이유", "cost": 15000}} ],
                        "Day 2": [ {{"name": "식당명", "type": "맛집 또는 카페", "description": "이유", "cost": 8000}} ]
                    }}
                    """
                    resp_food = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_food)
                    match_food = re.search(r'\{.*\}', resp_food.text, re.DOTALL)
                    if match_food:
                        st.session_state.food_recommendations = json.loads(match_food.group(0))
                        for day_label, foods in st.session_state.food_recommendations.items():
                            for f in foods: st.session_state.all_food_dict[f['name']] = f
                except Exception as e:
                    st.error(f"탐색 중 오류: {e}")

        if st.session_state.food_recommendations:
            st.markdown("---")
            for day_info in iti_data:
                day_label = f"Day {day_info['day']}"
                with st.expander(f"🍱 {day_label} 추천 리스트 (방문: {', '.join([p['name'] for p in day_info['route'] if '숙소' not in p['name']])})", expanded=True):
                    
                    custom_food_col1, custom_food_col2 = st.columns([4, 1])
                    with custom_food_col1: 
                        custom_food = st.text_input("수동 맛집/카페 추가", placeholder="예: 이치란 라멘 도톤보리점", key=f"custom_food_{day_label}", label_visibility="collapsed")
                    with custom_food_col2:
                        if st.button("➕ 추가", key=f"btn_add_food_{day_label}", use_container_width=True) and custom_food:
                            new_food = {"name": custom_food, "type": "수동추가", "description": "사용자가 직접 추가한 장소입니다.", "cost": 20000}
                            st.session_state.food_recommendations[day_label].append(new_food)
                            st.session_state.all_food_dict[custom_food] = new_food
                            st.rerun()
                    
                    foods = st.session_state.food_recommendations.get(day_label, [])
                    grid_cols = st.columns(3)
                    for idx, food in enumerate(foods):
                        with grid_cols[idx % 3]:
                            with st.container(border=True):
                                st.markdown(f"**{food['name']}**")
                                st.caption(f"{food['type']} | 💸 약 {food['cost']:,}원")
                                st.write(f"*{food['description']}*")
                                
                                is_food_selected = day_label in st.session_state.selected_food and food['name'] in st.session_state.selected_food[day_label]
                                st.checkbox("일정에 넣기", value=is_food_selected, key=f"chk_food_{day_label}_{food['name']}", on_change=toggle_food, args=(day_label, food['name']))

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ 식당 선택 완료! 4단계(최종 완성본) 보러 가기 ➔", type="primary", use_container_width=True):
            st.session_state.step = 4; st.rerun()

# ==========================================
# [4단계 화면] 최종 합체 & 엑셀 다운로드
# ==========================================
elif st.session_state.step == 4:
    if not st.session_state.optimized_itinerary:
        st.warning("동선이 완성되지 않았습니다.")
    else:
        st.markdown("## 🎉 나만의 맞춤 여행 완성본")
        st.caption("관광지 동선과 선택한 맛집이 모두 합쳐진 최종 일정표입니다.")
        
        iti_data = st.session_state.optimized_itinerary['itinerary']
        
        num_people = st.session_state.get('num_people', 2)
        travel_style = st.session_state.get('travel_style', "🎒 스탠다드 (보통)")
        dates = st.session_state.get('travel_dates', [datetime.date(2026, 4, 1), datetime.date(2026, 4, 5)])
        nights = max(1, (dates[1] - dates[0]).days)
        style_multiplier = 0.7 if "가성비" in travel_style else 1.5 if "플렉스" in travel_style else 1.0
        
        total_accommodation = int(nights * 80000 * style_multiplier * num_people)
        total_activity, total_food = 0, 0
        excel_data = []

        for day in iti_data:
            day_label = f"Day {day['day']}"
            st.markdown(f"### 🗓️ {day_label} ({day['date']}) - {day['theme_of_day']}")
            
            for step in day['route']:
                theme = st.session_state.all_places_dict.get(step['name'], {}).get('theme', '기타')
                if theme in ['테마파크/액티비티']: total_activity += int(80000 * num_people)
                elif theme in ['랜드마크', '쇼핑']: total_activity += int(10000 * num_people)
                
                is_hotel = st.session_state.get('basecamp_hotel') in step['name']
                icon = "🏨" if is_hotel else "📍"
                st.markdown(f"> **{icon} {step['name']}** -  *{step['reason']}*")
                excel_data.append({"일자": day_label, "날짜": day['date'], "구분": "관광지/숙소", "장소명": step['name'], "메모": step['reason']})

            if day_label in st.session_state.selected_food and len(st.session_state.selected_food[day_label]) > 0:
                st.markdown("**👇 방문 예정 맛집/카페**")
                for f_name in st.session_state.selected_food[day_label]:
                    f_info = st.session_state.all_food_dict.get(f_name, {"type": "맛집", "cost": 15000})
                    total_food += int(f_info.get('cost', 15000) * num_people)
                    st.success(f"🍔 **{f_name}** ({f_info.get('type', '')})")
                    excel_data.append({"일자": day_label, "날짜": day['date'], "구분": "맛집/카페", "장소명": f_name, "메모": "선택한 맛집"})
            
            st.divider()

        total_budget = total_accommodation + total_activity + total_food
        
        st.markdown("### 💳 최종 예상 경비 영수증")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("총 합계", f"{total_budget:,} 원")
        m_col2.metric("🏨 예상 숙박비", f"{total_accommodation:,} 원")
        m_col3.metric("🎢 관광/입장권", f"{total_activity:,} 원")
        m_col4.metric("🍔 식비/카페", f"{total_food:,} 원")
        
        st.markdown("<br>", unsafe_allow_html=True)
        df = pd.DataFrame(excel_data)
        csv = df.to_csv(index=False).encode('utf-8-sig') 
        
        st.download_button(
            label="📥 완벽한 일정표 엑셀(CSV)로 다운로드",
            data=csv,
            file_name='ZeroPlan_Itinerary.csv',
            mime='text/csv',
            type="primary",
            use_container_width=True
        )