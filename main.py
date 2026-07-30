import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

# ------------------------------------------------------------
# 기본 화면 설정
# ------------------------------------------------------------
st.set_page_config(page_title="영화 박스오피스 비교", layout="wide")
st.title("🎬 영화 박스오피스 비교")
st.caption("KOBIS(영화진흥위원회) 일별 박스오피스 데이터를 이용해 영화를 비교합니다.")

DAILY_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
MOVIE_INFO_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"

# 관람 등급 순위표를 만들려면 영화별 상세정보(등급)가 필요합니다.
# 이 정보는 dailyBoxOfficeList에 없어서, KOBIS의 영화 상세정보 API를
# movieCd(영화코드)로 추가 조회해서 가져옵니다. (dailyBoxOfficeList 응답에는
# movieCd가 포함되어 있습니다.)


# ------------------------------------------------------------
# 인증키는 코드에 쓰지 않고 스트림릿 시크릿(secrets)에서 불러옵니다.
# .streamlit/secrets.toml 또는 스트림릿 클라우드의 Secrets 설정에
#   KOBIS_KEY = "발급받은 인증키"
# 형태로 등록해 두어야 합니다.
# ------------------------------------------------------------
def get_api_key():
    try:
        return st.secrets["KOBIS_KEY"]
    except Exception:
        return None


def to_int(value, default=0):
    """문자열로 오는 숫자값을 안전하게 정수로 바꿔줍니다."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------
# 일별 박스오피스 목록 가져오기
# 반환값: (영화 리스트 또는 None, 오류 안내 메시지 또는 None)
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_daily_box_office(target_dt: str, api_key: str):
    params = {"key": api_key, "targetDt": target_dt}

    try:
        resp = requests.get(DAILY_URL, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        return None, f"KOBIS 서버에 요청하는 중 네트워크 오류가 발생했습니다.\n(자세한 내용: {e})"

    if resp.status_code != 200:
        return None, f"KOBIS 서버가 오류를 반환했습니다. (상태코드 {resp.status_code})"

    try:
        data = resp.json()
    except ValueError:
        return None, "KOBIS 응답을 해석할 수 없습니다. 잠시 후 다시 시도해 주세요."

    # 인증키가 틀려도 상태코드는 200이고, 대신 faultInfo 상자가 옵니다.
    if "faultInfo" in data:
        message = data["faultInfo"].get("message", "알 수 없는 오류")
        return None, (
            f"KOBIS에서 오류를 반환했습니다: {message}\n"
            "→ 스트림릿 시크릿에 등록한 KOBIS_KEY 값이 정확한지 확인해 주세요."
        )

    box_result = data.get("boxOfficeResult")
    if not box_result:
        return None, "응답에 boxOfficeResult가 없습니다. 조회 날짜를 다시 확인해 주세요."

    movie_list = box_result.get("dailyBoxOfficeList", [])
    if not movie_list:
        return None, (
            "해당 날짜의 박스오피스 데이터가 비어 있습니다.\n"
            "→ 아직 집계되지 않은 오늘/미래 날짜는 아닌지, 날짜 형식(yyyymmdd)이 맞는지 확인해 주세요."
        )

    return movie_list, None


# ------------------------------------------------------------
# 영화 상세정보(관람 등급) 가져오기 - 영화 한 편씩 조회
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_watch_grade(movie_cd: str, api_key: str):
    params = {"key": api_key, "movieCd": movie_cd}
    try:
        resp = requests.get(MOVIE_INFO_URL, params=params, timeout=10)
        data = resp.json()
    except Exception:
        return "정보 없음"

    if "faultInfo" in data:
        return "정보 없음"

    movie_info = data.get("movieInfoResult", {}).get("movieInfo")
    if not movie_info:
        return "정보 없음"

    audits = movie_info.get("audits", [])
    if not audits:
        return "정보 없음"

    return audits[0].get("watchGradeNm", "정보 없음")


# ------------------------------------------------------------
# 화면 구성 - 날짜 선택
# ------------------------------------------------------------
api_key = get_api_key()

if not api_key:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n"
        "→ 스트림릿 클라우드의 [Settings > Secrets]에 아래와 같이 등록해 주세요.\n\n"
        'KOBIS_KEY = "발급받은 인증키"'
    )
    st.stop()

# KOBIS는 보통 전날까지의 데이터가 집계되어 있으므로 기본값을 어제로 둡니다.
default_date = date.today() - timedelta(days=1)
selected_date = st.date_input("조회할 날짜를 선택하세요", value=default_date, max_value=default_date)
target_dt = selected_date.strftime("%Y%m%d")

fetch_clicked = st.button("박스오피스 조회하기")

if fetch_clicked:
    with st.spinner("KOBIS에서 박스오피스 데이터를 불러오는 중입니다..."):
        movie_list, error_msg = fetch_daily_box_office(target_dt, api_key)

    if error_msg:
        st.error(error_msg)
        st.stop()

    # -------------------------------------------------------
    # 받아온 데이터를 표로 다루기 좋게 정리
    # -------------------------------------------------------
    rows = []
    for m in movie_list:
        audi_cnt = to_int(m.get("audiCnt"))
        scrn_cnt = to_int(m.get("scrnCnt"))
        # 스크린수가 0이면 나눌 수 없으니 0으로 처리합니다.
        audi_per_screen = round(audi_cnt / scrn_cnt, 1) if scrn_cnt > 0 else 0

        rows.append(
            {
                "순위": to_int(m.get("rank")),
                "영화명": m.get("movieNm", ""),
                "movieCd": m.get("movieCd", ""),
                "개봉일": m.get("openDt", ""),
                "스크린수": scrn_cnt,
                "관객수": audi_cnt,
                "스크린당 관객수": audi_per_screen,
                "누적관객수": to_int(m.get("audiAcc")),
                "상영횟수": to_int(m.get("showCnt")),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        st.warning("표시할 영화 데이터가 없습니다. 날짜를 바꿔서 다시 시도해 주세요.")
        st.stop()

    # -------------------------------------------------------
    # 1) 스크린수 대비 관객수(스크린당 관객수) 상위 10개
    # -------------------------------------------------------
    st.subheader("📊 스크린당 관객수 상위 10개 영화")
    st.caption("스크린 하나당 몇 명이 봤는지를 기준으로, '적은 스크린으로도 많이 본' 영화를 찾아줍니다.")

    top10 = df.sort_values("스크린당 관객수", ascending=False).head(10).reset_index(drop=True)
    show_cols = ["순위", "영화명", "개봉일", "스크린수", "관객수", "스크린당 관객수", "누적관객수", "상영횟수"]
    st.dataframe(top10[show_cols], use_container_width=True, hide_index=True)

    # 막대그래프로도 한눈에 비교 (스트림릿 기본 차트라 별도 라이브러리 필요 없음)
    st.bar_chart(top10.set_index("영화명")["스크린당 관객수"])

    # -------------------------------------------------------
    # 2) 관람 등급에 따른 영화 순위
    # -------------------------------------------------------
    st.subheader("🎫 관람 등급별 영화 순위")
    st.caption(
        "일별 박스오피스 API에는 관람 등급 정보가 없어서, 영화별 상세정보를 추가로 조회해 등급을 붙였습니다."
    )

    with st.spinner("영화별 관람 등급 정보를 불러오는 중입니다..."):
        df["관람등급"] = df["movieCd"].apply(lambda code: fetch_watch_grade(code, api_key))

    grade_df = df.sort_values(["관람등급", "순위"])[
        ["관람등급", "순위", "영화명", "관객수", "스크린당 관객수"]
    ].reset_index(drop=True)

    grades = grade_df["관람등급"].unique().tolist()
    for grade in grades:
        st.markdown(f"**{grade}**")
        one_grade = grade_df[grade_df["관람등급"] == grade].reset_index(drop=True)
        st.dataframe(one_grade[["순위", "영화명", "관객수", "스크린당 관객수"]], use_container_width=True, hide_index=True)

else:
    st.info("날짜를 선택하고 '박스오피스 조회하기' 버튼을 눌러주세요.")
