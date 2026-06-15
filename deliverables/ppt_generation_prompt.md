너는 발표자료를 전문적으로 만드는 AI다. 아래 프로젝트 내용을 바탕으로 5~7분 발표용 PPT를 10매 내외로 제작해줘.

프로젝트명: Sleep Study Guard
주제: 공부 중 사용자가 잠드는 것을 웹캠으로 감지하고 깨워주는 웹 서비스

필수 조건:
- 발표자료는 10매 내외
- 서비스 핵심 소개, ML 모델의 역할, 아키텍처 구조 중심
- 발표 중 라이브 시연 오류를 방지하기 위해 실행 영상 삽입 슬라이드를 반드시 포함
- 디자인은 학생 프로젝트 발표용으로 깔끔하고 기술 중심적으로 구성
- 너무 많은 문장을 넣지 말고 핵심 키워드와 구조도 위주로 제작

사용 기술:
- Frontend: React, Vite, WebRTC getUserMedia, Canvas overlay
- Backend: FastAPI, Pydantic, SQLAlchemy ORM, SQLite
- Vision/ML: OpenCV, MediaPipe FaceMesh, scikit-learn RandomForestClassifier, joblib
- Modeling: CSV 특징 데이터 기반 학습, StandardScaler + RandomForest, model.joblib export

서비스 흐름:
1. 사용자가 과목을 입력하고 공부 세션 시작
2. React가 웹캠 프레임을 주기적으로 캡처
3. FastAPI가 프레임을 받아 MediaPipe FaceMesh로 얼굴/눈 랜드마크 추출
4. EAR, 눈 감김 지속 시간, 얼굴 방향 특징값 계산
5. RandomForest 모델이 awake/drowsy 예측
6. 졸음이면 화면 상태를 DROWSY로 표시하고 알림음 재생
7. 예측 결과와 특징값을 drowsiness_logs 테이블에 저장
8. 세션 종료 후 공부 시간, 졸음 횟수, 졸음 비율 통계 제공

DB 구조:
- users
- study_sessions
- drowsiness_logs
관계:
- users 1:N study_sessions
- study_sessions 1:N drowsiness_logs

핵심 API:
- GET /health
- GET /debug/runtime
- GET /users/default
- POST /study-sessions/start
- POST /study-sessions/{id}/end
- POST /drowsiness/predict
- POST /drowsiness/predict-frame
- GET /drowsiness/logs
- GET /stats/session/{id}

중요 트러블슈팅:
1. CORS처럼 보였던 오류의 실제 원인은 predict-frame 내부 500 오류였다. MediaPipe 최신 버전에서 mp.solutions.face_mesh가 없어 AttributeError가 발생했다. Python 3.11 가상환경을 만들고 mediapipe==0.10.14로 고정하여 해결했다.
2. 눈을 감아도 EAR 값이 변하지 않았다. OpenCV fallback의 눈 영역 추정 한계와 React setInterval의 stale state 문제가 원인이었다. closedSince를 useRef로 바꾸고 MediaPipe FaceMesh 기반 EAR 계산으로 복구했다.

슬라이드 구성 제안:
1. 제목: Sleep Study Guard
2. 문제 정의: 공부 중 졸음의 페인포인트
3. 서비스 핵심 기능: 웹캠 감지, 알림, 세션 기록, 통계
4. 전체 아키텍처: React - FastAPI - ML - DB 구조도
5. 데이터 흐름: 웹캠 프레임에서 졸음 로그 저장까지
6. ML 모델 역할: 특징값, RandomForest, awake/drowsy 분류
7. DB/ERD 요약: 3개 테이블과 1:N 관계
8. 핵심 API 및 화면 구성
9. 트러블슈팅: MediaPipe 버전 문제와 EAR 문제
10. 시연 영상 삽입 + 마무리/배운 점

시연 영상 슬라이드:
- 제목: 실행 시연
- 중앙에 동영상 삽입 영역
- 동영상 내용: 세션 시작 → 웹캠 박스 표시 → 눈 감김 → DROWSY 표시/알림 → 세션 종료 → 통계 확인

발표 톤:
- 기술 스택을 단순 나열하지 말고 “왜 이 기술을 사용했는지”를 설명
- ML 모델은 이미지 전체를 직접 분류하는 것이 아니라 FaceMesh/OpenCV에서 추출한 특징값을 분류한다는 점을 명확히 설명
- 트러블슈팅은 가장 중요한 파트로 1~2장 정도 비중 있게 작성
