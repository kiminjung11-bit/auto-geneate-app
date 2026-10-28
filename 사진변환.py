import json
import os
import re
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps

SIZE = 1080
BASE = Path(__file__).parent
SRC = BASE / "자료"
OUT = BASE / "완성"
TODAY = date.today().isoformat()
DAY_DIR = OUT / TODAY  # 그날 결과물을 모으는 폴더


LOGO_PATH = SRC / "로고.png"
LOGO_RATIO = 0.15   # 사진 가로 폭의 15%
LOGO_MARGIN = 40    # 가장자리에서 안쪽으로 띄울 거리
LOGO_OPACITY = 0.7  # 70%만 보이게


def load_logo():
    """로고 파일이 없거나 열 수 없으면 None을 돌려줘서 이 단계를 건너뛴다."""
    if not LOGO_PATH.exists():
        return None
    try:
        with Image.open(LOGO_PATH) as logo:
            logo = logo.convert("RGBA")
            w = round(SIZE * LOGO_RATIO)
            h = round(logo.height * w / logo.width)
            logo = logo.resize((w, h), Image.LANCZOS)
    except Exception:
        return None
    alpha = logo.getchannel("A").point(lambda a: round(a * LOGO_OPACITY))
    logo.putalpha(alpha)
    return logo


def add_logo(img, logo):
    x = SIZE - LOGO_MARGIN - logo.width
    y = SIZE - LOGO_MARGIN - logo.height
    img.paste(logo, (x, y), logo)
    return img


def next_number(prefix):
    """같은 날 이미 만든 파일이 있으면 그다음 번호부터 시작한다."""
    nums = [int(p.stem.split("_")[-1]) for p in DAY_DIR.glob(f"{prefix}_*.jpg")
            if p.stem.split("_")[-1].isdigit()]
    return max(nums, default=0) + 1


MODEL = "claude-sonnet-5-5"


def load_api_key():
    """환경변수 또는 폴더 안의 .env 파일에서 API 키를 찾는다."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    env_file = BASE / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"\'')
    return key


def read_first(folder, names):
    for name in names:
        f = folder / name
        if f.exists():
            return f.read_text(encoding="utf-8")
    return None


def make_copy():
    """가게 정보와 말투를 읽어 인스타 문구 3종 + 해시태그 10개를 홍보문구.txt로 저장한다."""
    info = read_first(SRC, ["가게 정보.txt", "가게정보.txt"])
    if info is None:
        print("'가게 정보.txt'가 없어서 홍보 문구는 건너뛰어요.")
        return
    key = load_api_key()
    if not key:
        print("API 키가 없어서 홍보 문구는 건너뛰어요. (키 넣는 방법은 안내를 확인해 주세요)")
        return

    voice = read_first(SRC, ["내 말투.txt"]) or ""
    prompt = f"""아래 가게 정보를 바탕으로 인스타그램 게시물 문구를 만들어 주세요.

[가게 정보]
{info}

[사장님이 평소 쓰는 글 (말투 참고용)]
{voice}

조건:
- 감성형 / 정보형 / 이벤트형, 3가지 버전
- 각 문구는 공백 포함 150자를 넘지 않게
- 이모지, 느낌표, 과장된 칭찬은 쓰지 않는다 (사장님은 평소 이모지를 쓰지 않음)

사장님 말투 규칙 (위 글을 분석한 결과):
- "~습니다"로 끝나는 정중하고 담백한 말투. 가끔 "~더라고요"가 섞이는 정도
- 한 문장은 10~20자 안팎으로 짧게. 생각 하나가 끝나면 줄을 바꾸고, 한 줄을 비운다
- 순서는 "있었던 일 → 지금 상황 → 앞으로 할 일", 마지막은 "~했습니다", "~하겠습니다"처럼 행동으로 끝낸다
- "조금", "생각보다", "그래도", "평소대로", "미리 말씀드립니다" 같은 표현을 자연스럽게 쓴다
- 자랑하지 않고 있는 그대로 말한다. "기다리고 있겠습니다", "~좋아요", "편하게 즐기세요" 같은 붙임성 있는 말은 쓰지 않는다
- 정보에 없는 내용(가격, 시간, 메뉴)을 지어내지 말 것
- 해시태그는 지역명 + 업종 + 메뉴를 조합해 정확히 10개 ('#' 포함)

JSON만 출력하세요. 형식:
{{"감성형": "...", "정보형": "...", "이벤트형": "...", "해시태그": ["#...", ...]}}"""

    import anthropic
    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=MODEL, max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        print("API 키가 올바르지 않아요. 키를 다시 확인해 주세요. 홍보 문구는 건너뜁니다.")
        return
    except anthropic.APIError as e:
        print(f"문구 만들기에 실패했어요 ({e}). 사진 변환 결과는 그대로예요.")
        return

    text = resp.content[0].text
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(re.search(r"\{.*\}", text, re.S).group())
        tags = " ".join(data["해시태그"])
        body = "\n\n".join(f"[{k}]\n{data[k]}" for k in ("감성형", "정보형", "이벤트형"))
        result = f"{body}\n\n[해시태그]\n{tags}\n"
    except (AttributeError, KeyError, ValueError):
        result = text  # 형식이 달라도 내용은 잃지 않도록 그대로 저장
    (DAY_DIR / "홍보문구.txt").write_text(result, encoding="utf-8")
    print(f"홍보 문구를 '완성/{TODAY}' 폴더의 홍보문구.txt에 저장했어요.")


def make_photos():
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    photos = sorted(p for p in SRC.iterdir()
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png")
                    and p.name != LOGO_PATH.name)
    if not photos:
        print("'자료' 폴더에 사진이 없어요.")
        return

    logo = load_logo()
    if logo is None:
        print("로고.png가 없어서 로고는 넣지 않고 진행해요.")

    prefix = TODAY
    n = next_number(prefix)
    for p in photos:
        with Image.open(p) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            # 가운데 기준으로 잘라서 정사각형으로 맞춤 (늘리지 않음)
            img = ImageOps.fit(img, (SIZE, SIZE), Image.LANCZOS, centering=(0.5, 0.5))
            if logo is not None:
                img = add_logo(img, logo)
            name = f"{prefix}_{n:02d}.jpg"
            img.save(DAY_DIR / name, "JPEG", quality=95)
        print(f"{p.name} -> {name}")
        n += 1
    print(f"끝! {len(photos)}장을 '완성' 폴더에 저장했어요.")


def main():
    make_photos()
    make_copy()


if __name__ == "__main__":
    main()
