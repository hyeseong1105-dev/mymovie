import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖")
st.title("🤖 AI 정보 선생님")

# 비밀 금고(secrets)에서 API 키를 꺼내 접속 준비
client = OpenAI(
    api_key=st.secrets["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# 말투마다 다른 성격 문장을 미리 준비
TONES = {
    "친절한 선생님": "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. 어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해",
    "시크한 전문가": "너는 군더더기 없이 핵심만 말하는 데이터 전문가야. 답은 세 문장 이내로, 반드시 순수 한국어로만 답해",
    "되물어보는 조교": "너는 정답을 바로 알려 주지 않는 조교야. 먼저 힌트를 하나 주고 되물어봐. 학생이 스스로 답을 말하면 그때 확인해 줘. 반드시 순수 한국어로만 답해",
}

tone = st.sidebar.radio("말투 고르기", list(TONES))
persona = st.sidebar.text_area("성격 문장 직접 고치기", TONES[tone], height=140)

if st.sidebar.button("대화 지우기"):
    st.session_state.messages = []
    st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

# 지금까지의 대화를 말풍선으로 다시 그리기
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("궁금한 것을 물어보세요!")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 성격 문장을 맨 앞에 붙여 보내면 진행 중인 대화에도 다음 답부터 반영된다
    payload = [{"role": "system", "content": persona}] + st.session_state.messages

    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model="gemini-3.8-flash",
                messages=payload,
                stream=True,
            )
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream if chunk.choices
            )
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.error(f"에러: {e}")
